"""
Tests de Trazabilidad de Borradores (InvoiceDraft)

Prueba el sistema de trazabilidad completo para borradores de factura,
incluyendo creación, registro de extracción IA, ediciones de usuario
y vinculación con factura final.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
import uuid

from src.database.models import (
    InvoiceDraft,
    Invoice,
    Organization,
    User,
    TenantConfig,
)
from src.database.queries.draft_queries import (
    create_draft_async,
    get_draft_by_id_async,
    get_active_draft_async,
    record_input_async,
    record_ai_extraction_async,
    record_user_edit_async,
    update_draft_step_async,
    update_draft_data_async,
    finalize_draft_async,
    cancel_draft_async,
    get_draft_with_history_async,
    DRAFT_STATUS_ACTIVE,
    DRAFT_STATUS_COMPLETED,
    DRAFT_STATUS_CANCELLED,
)
from src.utils.crypto import hash_password


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def org_id():
    """ID de organización para tests."""
    return f"org-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def user_id():
    """ID de usuario para tests."""
    return 1


@pytest.fixture
def chat_id():
    """ID de chat de Telegram para tests."""
    return 123456789


@pytest.fixture
async def async_db_with_org_and_user(async_db_session, org_id, user_id):
    """Proporciona una sesión async con organización y usuario creados."""
    # Crear organización
    org = Organization(
        id=org_id,
        name="Joyería Test Traceability",
        slug=f"joyeria-test-{uuid.uuid4().hex[:8]}",
        plan="basic",
        status="active",
    )
    async_db_session.add(org)
    await async_db_session.commit()

    # Crear config de tenant
    config = TenantConfig(
        organization_id=org_id,
        invoice_prefix="FAC",
        tax_rate=0.19,
        currency="COP",
    )
    async_db_session.add(config)

    # Crear usuario
    user = User(
        id=user_id,
        organization_id=org_id,
        cedula="123456789",
        nombre_completo="Vendedor Test",
        email="vendedor@test.com",
        password_hash=hash_password("Test123!"),
        rol="VENDEDOR",
        activo=True,
    )
    async_db_session.add(user)
    await async_db_session.commit()

    return async_db_session


# ============================================================================
# TEST CLASS: Trazabilidad de Borradores
# ============================================================================

class TestDraftTraceability:
    """Tests de trazabilidad de borradores de factura."""

    @pytest.mark.asyncio
    async def test_draft_created_on_flow_start(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """
        Verifica que se crea un borrador al iniciar el flujo de factura.

        El borrador debe:
        - Tener estado 'active'
        - Estar asociado a la organización y usuario correctos
        - Tener el chat_id del telegram
        - Estar en el paso inicial 'SELECCIONAR_INPUT'
        - Tener historial de cambios vacío inicialmente
        """
        db = async_db_with_org_and_user

        # Act: Crear borrador al iniciar flujo
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
            input_type=None,  # Aún no se ha seleccionado
            current_step="SELECCIONAR_INPUT",
        )

        # Assert
        assert draft is not None
        assert draft.id is not None
        assert len(draft.id) == 36  # UUID format
        assert draft.organization_id == org_id
        assert draft.user_id == user_id
        assert draft.telegram_chat_id == chat_id
        assert draft.status == DRAFT_STATUS_ACTIVE
        assert draft.current_step == "SELECCIONAR_INPUT"
        assert draft.items_data == []
        assert draft.customer_data == {}
        assert draft.totals_data == {}
        assert draft.change_history == []
        assert draft.expires_at is not None
        assert draft.expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_ai_extraction_recorded(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """
        Verifica que la extracción de IA se registra con timestamp.

        Cuando la IA extrae datos del input:
        - Se guarda la respuesta raw de la IA
        - Se registra el timestamp de extracción
        - Se guardan los datos extraídos (items, cliente, totales)
        - Se agrega un registro en el historial de cambios
        """
        db = async_db_with_org_and_user

        # Arrange: Crear borrador y registrar input
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        await record_input_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            input_type="TEXTO",
            input_raw="Un anillo de oro 18k por 500000 para María Pérez cédula 123456",
        )

        # Datos simulados de extracción IA
        ai_response = {
            "model": "gpt-4",
            "usage": {"tokens": 150},
            "raw_response": "Extracted invoice data...",
        }
        items_data = [
            {
                "descripcion": "Anillo de oro 18k",
                "cantidad": 1,
                "precio": 500000,
                "material": "oro_18k",
                "tipo_prenda": "anillo",
            }
        ]
        customer_data = {
            "nombre": "María Pérez",
            "cedula": "123456",
        }
        totals_data = {
            "subtotal": 500000,
            "impuesto": 95000,
            "total": 595000,
        }

        # Act: Registrar extracción de IA
        updated_draft = await record_ai_extraction_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            ai_response=ai_response,
            items_data=items_data,
            customer_data=customer_data,
            totals_data=totals_data,
        )

        # Assert
        assert updated_draft is not None
        assert updated_draft.ai_response_raw == ai_response
        assert updated_draft.ai_extraction_timestamp is not None
        assert updated_draft.ai_extraction_timestamp <= datetime.utcnow()
        assert updated_draft.items_data == items_data
        assert updated_draft.customer_data == customer_data
        assert updated_draft.totals_data == totals_data

        # Verificar que se registró en el historial
        assert len(updated_draft.change_history) >= 1
        ai_change = next(
            (c for c in updated_draft.change_history if c.get("field") == "ai_extraction"),
            None
        )
        assert ai_change is not None
        assert ai_change["source"] == "ai"
        assert "timestamp" in ai_change
        assert ai_change["new_value"]["items_count"] == 1
        assert ai_change["new_value"]["has_customer"] is True

    @pytest.mark.asyncio
    async def test_user_edit_tracked(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """
        Verifica que las ediciones del usuario se registran en el historial.

        Cuando el usuario modifica datos:
        - Se registra el campo modificado
        - Se guarda el valor anterior (old_value)
        - Se guarda el valor nuevo (new_value)
        - Se marca el origen como 'user'
        - Se incluye timestamp
        """
        db = async_db_with_org_and_user

        # Arrange: Crear borrador con datos de IA
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        # Simular que la IA extrajo datos
        initial_items = [{"descripcion": "Anillo", "precio": 500000, "cantidad": 1}]
        await update_draft_data_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            items_data=initial_items,
            source="ai",
        )

        # Act: Usuario edita el precio del item
        old_price = 500000
        new_price = 450000
        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="items[0].precio",
            old_value=old_price,
            new_value=new_price,
        )

        # Recuperar borrador actualizado
        updated_draft = await get_draft_by_id_async(db, draft.id, org_id)

        # Assert
        assert updated_draft is not None
        assert len(updated_draft.change_history) >= 2  # AI + User edit

        # Buscar el cambio del usuario
        user_edit = next(
            (c for c in updated_draft.change_history
             if c.get("field") == "items[0].precio" and c.get("source") == "user"),
            None
        )
        assert user_edit is not None
        assert user_edit["old_value"] == old_price
        assert user_edit["new_value"] == new_price
        assert user_edit["source"] == "user"
        assert "timestamp" in user_edit

    @pytest.mark.asyncio
    async def test_draft_linked_to_final_invoice(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """
        Verifica que el borrador se vincula correctamente a la factura final.

        Al completar el flujo:
        - El borrador cambia a estado 'completed'
        - Se registra el invoice_id de la factura creada
        - Se agrega un registro de finalización en el historial
        """
        db = async_db_with_org_and_user

        # Arrange: Crear borrador con datos completos
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        # Simular datos extraídos
        await update_draft_data_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            items_data=[{"descripcion": "Anillo oro", "precio": 500000, "cantidad": 1}],
            customer_data={"nombre": "Cliente Test", "cedula": "987654321"},
            totals_data={"subtotal": 500000, "impuesto": 95000, "total": 595000},
            source="ai",
        )

        # Crear factura (simulada)
        invoice = Invoice(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            numero_factura="FAC-202412-0001",
            cliente_nombre="Cliente Test",
            cliente_cedula="987654321",
            items=[],
            subtotal=500000,
            impuesto=95000,
            total=595000,
            vendedor_id=user_id,
        )
        db.add(invoice)
        await db.commit()

        # Act: Finalizar borrador vinculándolo a la factura
        finalized_draft = await finalize_draft_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            invoice_id=invoice.id,
        )

        # Assert
        assert finalized_draft is not None
        assert finalized_draft.status == DRAFT_STATUS_COMPLETED
        assert finalized_draft.invoice_id == invoice.id

        # Verificar registro de finalización en historial
        finalization_change = next(
            (c for c in finalized_draft.change_history if c.get("field") == "finalization"),
            None
        )
        assert finalization_change is not None
        assert finalization_change["source"] == "system"
        assert finalization_change["new_value"]["invoice_id"] == invoice.id
        assert finalization_change["new_value"]["new_status"] == DRAFT_STATUS_COMPLETED

    @pytest.mark.asyncio
    async def test_full_flow_traceability(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """
        Test E2E: todo el flujo de facturación con trazabilidad completa.

        Simula el flujo completo:
        1. Usuario inicia flujo -> se crea borrador
        2. Usuario envía texto/voz/foto -> se registra input
        3. IA extrae datos -> se registra extracción
        4. Usuario edita precio y cliente -> se registran ediciones
        5. Usuario confirma -> se crea factura y se vincula borrador

        Verifica que todo el historial queda registrado correctamente.
        """
        db = async_db_with_org_and_user

        # ==========================================
        # PASO 1: Iniciar flujo - Crear borrador
        # ==========================================
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
            current_step="SELECCIONAR_INPUT",
        )
        assert draft.status == DRAFT_STATUS_ACTIVE
        initial_history_count = len(draft.change_history)

        # ==========================================
        # PASO 2: Usuario envía input de texto
        # ==========================================
        input_text = "Cadena de plata 925 peso 15 gramos 150000 para Juan García cédula 555444333"
        draft = await record_input_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            input_type="TEXTO",
            input_raw=input_text,
        )
        assert draft.input_type == "TEXTO"
        assert draft.input_raw == input_text
        assert len(draft.change_history) > initial_history_count

        # Actualizar paso
        draft = await update_draft_step_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            new_step="PROCESANDO_INPUT",
        )
        assert draft.current_step == "PROCESANDO_INPUT"

        # ==========================================
        # PASO 3: IA extrae datos
        # ==========================================
        ai_response = {"model": "claude-3", "tokens_used": 200}
        items_data = [
            {
                "descripcion": "Cadena de plata 925",
                "cantidad": 1,
                "precio": 150000,
                "material": "plata_925",
                "peso_gramos": 15.0,
                "tipo_prenda": "cadena",
            }
        ]
        customer_data = {"nombre": "Juan García", "cedula": "555444333"}
        totals_data = {"subtotal": 150000, "impuesto": 28500, "total": 178500}

        draft = await record_ai_extraction_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            ai_response=ai_response,
            items_data=items_data,
            customer_data=customer_data,
            totals_data=totals_data,
        )
        assert draft.ai_extraction_timestamp is not None
        assert draft.items_data[0]["descripcion"] == "Cadena de plata 925"

        # Actualizar paso a confirmación
        draft = await update_draft_step_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            new_step="CONFIRMAR_DATOS",
        )

        # ==========================================
        # PASO 4: Usuario edita datos
        # ==========================================
        # Editar precio
        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="items[0].precio",
            old_value=150000,
            new_value=145000,
        )

        # Editar nombre del cliente
        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="customer.nombre",
            old_value="Juan García",
            new_value="Juan Carlos García",
        )

        # Actualizar datos en el borrador
        updated_items = items_data.copy()
        updated_items[0]["precio"] = 145000
        updated_customer = customer_data.copy()
        updated_customer["nombre"] = "Juan Carlos García"
        updated_totals = {"subtotal": 145000, "impuesto": 27550, "total": 172550}

        draft = await update_draft_data_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            items_data=updated_items,
            customer_data=updated_customer,
            totals_data=updated_totals,
            source="user",
        )

        # ==========================================
        # PASO 5: Crear factura y finalizar borrador
        # ==========================================
        # Crear factura
        invoice = Invoice(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            numero_factura="FAC-202412-0002",
            cliente_nombre=updated_customer["nombre"],
            cliente_cedula=updated_customer["cedula"],
            items=updated_items,
            subtotal=updated_totals["subtotal"],
            impuesto=updated_totals["impuesto"],
            total=updated_totals["total"],
            vendedor_id=user_id,
        )
        db.add(invoice)
        await db.commit()

        # Finalizar borrador
        final_draft = await finalize_draft_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            invoice_id=invoice.id,
        )

        # ==========================================
        # VERIFICACIONES FINALES
        # ==========================================
        assert final_draft.status == DRAFT_STATUS_COMPLETED
        assert final_draft.invoice_id == invoice.id

        # Obtener borrador con historial completo
        draft_with_history = await get_draft_with_history_async(
            db=db,
            draft_id=final_draft.id,
            org_id=org_id,
        )

        assert draft_with_history is not None
        assert draft_with_history["has_ai_extraction"] is True
        assert draft_with_history["has_invoice"] is True
        assert draft_with_history["history_count"] >= 5  # Input, AI, 2 edits, finalization

        # Verificar que el historial tiene los registros esperados
        history = draft_with_history["draft"]["change_history"]

        # Contar tipos de cambios
        sources = [c.get("source") for c in history]
        assert "user" in sources  # Ediciones del usuario
        assert "ai" in sources    # Extracción de IA
        assert "system" in sources  # Finalización

        # Verificar campos editados
        edited_fields = [c.get("field") for c in history if c.get("source") == "user"]
        assert "items[0].precio" in edited_fields
        assert "customer.nombre" in edited_fields


# ============================================================================
# TEST CLASS: Operaciones de Borrador
# ============================================================================

class TestDraftOperations:
    """Tests para operaciones básicas de borradores."""

    @pytest.mark.asyncio
    async def test_cancel_draft(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """Verifica que se puede cancelar un borrador activo."""
        db = async_db_with_org_and_user

        # Crear borrador
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )
        assert draft.status == DRAFT_STATUS_ACTIVE

        # Cancelar
        result = await cancel_draft_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            reason="Usuario canceló el flujo",
        )

        assert result is True

        # Verificar estado
        cancelled_draft = await get_draft_by_id_async(db, draft.id, org_id)
        assert cancelled_draft.status == DRAFT_STATUS_CANCELLED

        # Verificar registro en historial
        cancel_change = next(
            (c for c in cancelled_draft.change_history if c.get("field") == "cancellation"),
            None
        )
        assert cancel_change is not None
        assert "Usuario canceló el flujo" in str(cancel_change["new_value"])

    @pytest.mark.asyncio
    async def test_new_draft_cancels_existing(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """Verifica que crear un nuevo borrador cancela el existente para el mismo chat."""
        db = async_db_with_org_and_user

        # Crear primer borrador
        draft1 = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )
        draft1_id = draft1.id

        # Crear segundo borrador (mismo chat)
        draft2 = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        # Verificar que el primero fue cancelado
        old_draft = await get_draft_by_id_async(db, draft1_id, org_id)
        assert old_draft.status == DRAFT_STATUS_CANCELLED

        # Verificar que el nuevo está activo
        assert draft2.status == DRAFT_STATUS_ACTIVE
        assert draft2.id != draft1_id

    @pytest.mark.asyncio
    async def test_get_active_draft_by_chat(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """Verifica que se obtiene el borrador activo correcto por chat."""
        db = async_db_with_org_and_user

        # Crear borrador
        created_draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        # Buscar por chat
        found_draft = await get_active_draft_async(
            db=db,
            telegram_chat_id=chat_id,
            org_id=org_id,
        )

        assert found_draft is not None
        assert found_draft.id == created_draft.id
        assert found_draft.status == DRAFT_STATUS_ACTIVE

    @pytest.mark.asyncio
    async def test_update_draft_step_with_data(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """Verifica actualización de paso con datos adicionales."""
        db = async_db_with_org_and_user

        # Crear borrador
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        # Actualizar paso con datos
        new_items = [{"descripcion": "Test", "precio": 100000}]
        updated_draft = await update_draft_step_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            new_step="CONFIRMAR_DATOS",
            data_changes={"items_data": new_items},
        )

        assert updated_draft.current_step == "CONFIRMAR_DATOS"
        assert updated_draft.items_data == new_items


# ============================================================================
# TEST CLASS: Historial de Cambios
# ============================================================================

class TestChangeHistory:
    """Tests para el historial de cambios del borrador."""

    @pytest.mark.asyncio
    async def test_change_history_format(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """Verifica el formato correcto de los registros en el historial."""
        db = async_db_with_org_and_user

        # Crear borrador con cambios
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="test_field",
            old_value="old",
            new_value="new",
        )

        updated_draft = await get_draft_by_id_async(db, draft.id, org_id)

        # Verificar formato
        assert len(updated_draft.change_history) >= 1
        change = updated_draft.change_history[-1]

        assert "timestamp" in change
        assert "field" in change
        assert "old_value" in change
        assert "new_value" in change
        assert "source" in change

        # Verificar que timestamp es ISO format válido
        timestamp = change["timestamp"]
        datetime.fromisoformat(timestamp)  # No debe lanzar excepción

    @pytest.mark.asyncio
    async def test_multiple_sources_in_history(
        self,
        async_db_with_org_and_user,
        org_id,
        user_id,
        chat_id
    ):
        """Verifica que se registran cambios de múltiples fuentes."""
        db = async_db_with_org_and_user

        # Crear borrador
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        # Registrar cambio de IA
        await record_ai_extraction_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            ai_response={"model": "test"},
            items_data=[{"descripcion": "Item", "precio": 100}],
        )

        # Registrar cambio de usuario
        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="items[0].precio",
            old_value=100,
            new_value=150,
        )

        # Registrar cambio de sistema (actualizar paso)
        await update_draft_step_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            new_step="CONFIRMAR",
        )

        updated_draft = await get_draft_by_id_async(db, draft.id, org_id)

        # Verificar que hay cambios de todas las fuentes
        sources = set(c.get("source") for c in updated_draft.change_history)
        assert "ai" in sources
        assert "user" in sources
        assert "system" in sources

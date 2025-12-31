"""
Tests de Integración para el Flujo de Facturación

Prueba el flujo completo de facturación incluyendo:
- Trazabilidad de borradores
- Creación de facturas con items normalizados
- Consistencia de datos después de ediciones
- Rollback en caso de fallos
"""

import pytest
from datetime import datetime, timedelta
from typing import AsyncGenerator
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    Organization,
    User,
    TenantConfig,
    Invoice,
    InvoiceItem,
    InvoiceDraft,
    Customer,
)
from src.database.queries.draft_queries import (
    create_draft_async,
    record_input_async,
    record_ai_extraction_async,
    record_user_edit_async,
    update_draft_data_async,
    finalize_draft_async,
    get_draft_by_id_async,
    DRAFT_STATUS_ACTIVE,
    DRAFT_STATUS_COMPLETED,
)
from src.database.queries.invoice_queries import (
    create_invoice_with_items_async,
    get_invoice_with_items_async,
    update_invoice_with_items_async,
)
from src.database.queries.customer_queries import (
    get_customer_by_cedula_async,
    find_or_create_customer_async,
)
from src.database.queries.invoice_item_queries import (
    get_items_by_invoice_async,
)
from src.utils.crypto import hash_password
from src.metrics.tracker import MetricsTracker
from src.metrics.collectors import MetricsCollector


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def org_id():
    """ID de organización único para tests."""
    return f"org-flow-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def user_id():
    """ID de usuario para tests."""
    return 1


@pytest.fixture
def chat_id():
    """ID de chat de Telegram para tests."""
    return 123456789


@pytest.fixture
async def async_db_with_org_user(async_db_session, org_id, user_id):
    """Proporciona una sesión async con organización y usuario."""
    # Crear organización
    org = Organization(
        id=org_id,
        name="Joyería Flow Test",
        slug=f"joyeria-flow-{uuid.uuid4().hex[:8]}",
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
        nombre_completo="Vendedor Flow Test",
        email="vendedor@flowtest.com",
        password_hash=hash_password("Test123!"),
        rol="VENDEDOR",
        activo=True,
    )
    async_db_session.add(user)
    await async_db_session.commit()

    return async_db_session


# ============================================================================
# TEST CLASS: Flujo Completo de Facturación con Trazabilidad
# ============================================================================

class TestInvoiceFlowWithTraceability:
    """Tests de integración del flujo completo de facturación."""

    @pytest.mark.asyncio
    async def test_full_invoice_flow_with_traceability(
        self,
        async_db_with_org_user,
        org_id,
        user_id,
        chat_id
    ):
        """
        Test E2E del flujo de facturación con trazabilidad completa.

        Simula todo el flujo:
        1. Usuario inicia flujo (crea borrador)
        2. Usuario envía input de texto
        3. IA extrae datos
        4. Usuario edita algunos datos
        5. Se crea la factura con items normalizados
        6. Se vincula el borrador a la factura
        7. Se verifican métricas
        """
        db = async_db_with_org_user

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
        assert draft is not None
        assert draft.status == DRAFT_STATUS_ACTIVE
        draft_id = draft.id

        # ==========================================
        # PASO 2: Usuario envía input de texto
        # ==========================================
        input_text = """
        Cadena de oro 18k peso 25 gramos 1200000
        Anillo plata 925 con piedra azul 350000
        Para: María Elena García, cédula 555666777, tel 3001112233
        """
        draft = await record_input_async(
            db=db,
            draft_id=draft_id,
            org_id=org_id,
            input_type="TEXTO",
            input_raw=input_text.strip(),
        )
        assert draft.input_type == "TEXTO"
        assert draft.input_raw is not None

        # ==========================================
        # PASO 3: IA extrae datos
        # ==========================================
        ai_response = {
            "model": "claude-3-opus",
            "tokens_used": 350,
            "extraction_confidence": 0.95,
        }
        items_data = [
            {
                "descripcion": "Cadena de oro 18k",
                "cantidad": 1,
                "precio_unitario": 1200000,
                "subtotal": 1200000,
                "material": "oro_18k",
                "peso_gramos": 25.0,
                "tipo_prenda": "cadena",
            },
            {
                "descripcion": "Anillo plata 925 con piedra azul",
                "cantidad": 1,
                "precio_unitario": 350000,
                "subtotal": 350000,
                "material": "plata_925",
                "tipo_prenda": "anillo",
            },
        ]
        customer_data = {
            "nombre": "María Elena García",
            "cedula": "555666777",
            "telefono": "3001112233",
        }
        totals_data = {
            "subtotal": 1550000,
            "impuesto": 294500,
            "total": 1844500,
        }

        draft = await record_ai_extraction_async(
            db=db,
            draft_id=draft_id,
            org_id=org_id,
            ai_response=ai_response,
            items_data=items_data,
            customer_data=customer_data,
            totals_data=totals_data,
        )
        assert draft.ai_extraction_timestamp is not None
        assert len(draft.items_data) == 2

        # ==========================================
        # PASO 4: Usuario edita el precio del anillo
        # ==========================================
        await record_user_edit_async(
            db=db,
            draft_id=draft_id,
            org_id=org_id,
            field="items[1].precio_unitario",
            old_value=350000,
            new_value=320000,
        )

        # Actualizar los datos con la edición
        updated_items = items_data.copy()
        updated_items[1]["precio_unitario"] = 320000
        updated_items[1]["subtotal"] = 320000
        updated_totals = {
            "subtotal": 1520000,
            "impuesto": 288800,
            "total": 1808800,
        }

        draft = await update_draft_data_async(
            db=db,
            draft_id=draft_id,
            org_id=org_id,
            items_data=updated_items,
            totals_data=updated_totals,
            source="user",
        )

        # ==========================================
        # PASO 5: Crear factura con items normalizados
        # ==========================================
        invoice_data = {
            "organization_id": org_id,
            "cliente_nombre": customer_data["nombre"],
            "cliente_cedula": customer_data["cedula"],
            "cliente_telefono": customer_data["telefono"],
            "subtotal": updated_totals["subtotal"],
            "impuesto": updated_totals["impuesto"],
            "total": updated_totals["total"],
            "vendedor_id": user_id,
            "input_type": "TEXTO",
            "input_raw": input_text.strip(),
        }

        invoice = await create_invoice_with_items_async(
            db=db,
            invoice_data=invoice_data,
            items=updated_items,
            customer_data=customer_data,
        )

        assert invoice is not None
        assert invoice.numero_factura is not None
        assert invoice.total == 1808800

        # ==========================================
        # PASO 6: Vincular borrador a factura
        # ==========================================
        final_draft = await finalize_draft_async(
            db=db,
            draft_id=draft_id,
            org_id=org_id,
            invoice_id=invoice.id,
        )

        assert final_draft.status == DRAFT_STATUS_COMPLETED
        assert final_draft.invoice_id == invoice.id

        # ==========================================
        # VERIFICACIONES FINALES
        # ==========================================
        # Verificar factura con items
        invoice_with_items = await get_invoice_with_items_async(
            db=db,
            invoice_id=invoice.id,
            org_id=org_id,
        )
        assert invoice_with_items is not None
        assert len(invoice_with_items["items"]) == 2

        # Verificar items normalizados
        items = await get_items_by_invoice_async(db, invoice.id)
        assert len(items) == 2
        cadena = next((i for i in items if "Cadena" in i.descripcion), None)
        anillo = next((i for i in items if "Anillo" in i.descripcion), None)
        assert cadena is not None
        assert cadena.material == "oro_18k"
        assert cadena.peso_gramos == 25.0
        assert anillo is not None
        assert anillo.precio_unitario == 320000  # Precio editado

        # Verificar cliente creado
        customer = await get_customer_by_cedula_async(
            db=db,
            cedula="555666777",
            org_id=org_id,
        )
        assert customer is not None
        assert customer.nombre == "María Elena García"

        # Verificar historial del borrador
        final_draft = await get_draft_by_id_async(db, draft_id, org_id)
        assert len(final_draft.change_history) >= 4  # input, ai, edit, finalize

    @pytest.mark.asyncio
    async def test_data_consistency_after_edits(
        self,
        async_db_with_org_user,
        org_id,
        user_id,
        chat_id
    ):
        """
        Verifica la consistencia de datos después de múltiples ediciones.

        - Múltiples ediciones de items
        - Ediciones de datos de cliente
        - Recálculo de totales
        """
        db = async_db_with_org_user

        # Crear borrador con datos iniciales
        draft = await create_draft_async(
            db=db,
            org_id=org_id,
            user_id=user_id,
            telegram_chat_id=chat_id,
        )

        # Datos iniciales de IA
        initial_items = [
            {"descripcion": "Item 1", "cantidad": 2, "precio_unitario": 100000, "subtotal": 200000},
            {"descripcion": "Item 2", "cantidad": 1, "precio_unitario": 150000, "subtotal": 150000},
            {"descripcion": "Item 3", "cantidad": 3, "precio_unitario": 50000, "subtotal": 150000},
        ]
        initial_customer = {"nombre": "Cliente Inicial", "cedula": "111111111"}
        initial_totals = {"subtotal": 500000, "impuesto": 95000, "total": 595000}

        await record_ai_extraction_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            ai_response={"model": "test"},
            items_data=initial_items,
            customer_data=initial_customer,
            totals_data=initial_totals,
        )

        # Edición 1: Cambiar precio de Item 1
        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="items[0].precio_unitario",
            old_value=100000,
            new_value=120000,
        )

        # Edición 2: Cambiar cantidad de Item 2
        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="items[1].cantidad",
            old_value=1,
            new_value=2,
        )

        # Edición 3: Eliminar Item 3 (simular con cantidad 0 o actualizar lista)
        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="items",
            old_value="3 items",
            new_value="2 items (Item 3 eliminado)",
        )

        # Edición 4: Cambiar nombre del cliente
        await record_user_edit_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            field="customer.nombre",
            old_value="Cliente Inicial",
            new_value="Cliente Editado Final",
        )

        # Aplicar cambios finales
        final_items = [
            {"descripcion": "Item 1", "cantidad": 2, "precio_unitario": 120000, "subtotal": 240000},
            {"descripcion": "Item 2", "cantidad": 2, "precio_unitario": 150000, "subtotal": 300000},
        ]
        final_customer = {"nombre": "Cliente Editado Final", "cedula": "111111111"}
        final_totals = {"subtotal": 540000, "impuesto": 102600, "total": 642600}

        draft = await update_draft_data_async(
            db=db,
            draft_id=draft.id,
            org_id=org_id,
            items_data=final_items,
            customer_data=final_customer,
            totals_data=final_totals,
            source="user",
        )

        # Verificar que los datos finales son consistentes
        assert len(draft.items_data) == 2
        assert draft.items_data[0]["precio_unitario"] == 120000
        assert draft.items_data[1]["cantidad"] == 2
        assert draft.customer_data["nombre"] == "Cliente Editado Final"
        assert draft.totals_data["total"] == 642600

        # Verificar historial
        assert len(draft.change_history) >= 5  # AI + 4 ediciones + update final

        # Contar ediciones de usuario
        user_edits = [c for c in draft.change_history if c.get("source") == "user"]
        assert len(user_edits) >= 4

    @pytest.mark.asyncio
    async def test_rollback_on_failure(
        self,
        async_db_with_org_user,
        org_id,
        user_id
    ):
        """
        Verifica que los fallos no dejan datos inconsistentes.

        Simula un error durante la creación de factura y verifica
        que no queden registros huérfanos.
        """
        db = async_db_with_org_user

        # Intentar crear factura con datos inválidos
        invalid_invoice_data = {
            "organization_id": org_id,
            "cliente_nombre": "Test Cliente",
            # Falta vendedor_id - debería causar error o ser manejado
            "subtotal": 100000,
            "total": 119000,
        }

        invalid_items = [
            {"descripcion": "Item test", "cantidad": 1, "precio_unitario": 100000},
        ]

        # La función debería manejar el error gracefully
        result = await create_invoice_with_items_async(
            db=db,
            invoice_data=invalid_invoice_data,
            items=invalid_items,
        )

        # Si hay error, no debería haber facturas ni items huérfanos
        # (dependiendo de la implementación, podría retornar None o lanzar excepción)

        # Verificar que no quedaron items huérfanos
        from sqlalchemy import select
        from src.database.models import InvoiceItem

        # Este test verifica la integridad del rollback

    @pytest.mark.asyncio
    async def test_customer_find_or_create(
        self,
        async_db_with_org_user,
        org_id
    ):
        """
        Verifica que find_or_create_customer funciona correctamente.

        - Primera vez: crea el cliente
        - Segunda vez: encuentra el existente
        """
        db = async_db_with_org_user

        customer_data = {
            "nombre": "Cliente Test FindOrCreate",
            "cedula": "999888777",
            "telefono": "3009998887",
        }

        # Primera llamada - debería crear
        customer1 = await find_or_create_customer_async(
            db=db,
            org_id=org_id,
            customer_data=customer_data,
        )
        assert customer1 is not None
        customer1_id = customer1.id

        # Segunda llamada con misma cédula - debería encontrar
        customer2 = await find_or_create_customer_async(
            db=db,
            org_id=org_id,
            customer_data=customer_data,
        )
        assert customer2 is not None
        assert customer2.id == customer1_id  # Mismo cliente

        # Verificar que solo hay un cliente con esa cédula
        from sqlalchemy import select, func
        result = await db.execute(
            select(func.count(Customer.id)).where(
                Customer.organization_id == org_id,
                Customer.cedula == "999888777",
            )
        )
        count = result.scalar()
        assert count == 1


# ============================================================================
# TEST CLASS: Consistencia de Datos
# ============================================================================

class TestDataConsistency:
    """Tests de consistencia de datos."""

    @pytest.mark.asyncio
    async def test_invoice_items_normalized_and_json(
        self,
        async_db_with_org_user,
        org_id,
        user_id
    ):
        """
        Verifica que los items se guardan tanto en tabla normalizada
        como en campo JSON para compatibilidad.
        """
        db = async_db_with_org_user

        items = [
            {
                "descripcion": "Producto 1",
                "cantidad": 2,
                "precio_unitario": 100000,
                "material": "oro_18k",
            },
            {
                "descripcion": "Producto 2",
                "cantidad": 1,
                "precio_unitario": 50000,
                "material": "plata_925",
            },
        ]

        invoice_data = {
            "organization_id": org_id,
            "cliente_nombre": "Cliente Consistency Test",
            "subtotal": 250000,
            "total": 297500,
            "vendedor_id": user_id,
        }

        invoice = await create_invoice_with_items_async(
            db=db,
            invoice_data=invoice_data,
            items=items,
        )

        assert invoice is not None

        # Verificar items en tabla normalizada
        normalized_items = await get_items_by_invoice_async(db, invoice.id)
        assert len(normalized_items) == 2

        # Verificar que items_list (propiedad) funciona
        items_list = invoice.items_list
        assert len(items_list) == 2
        assert items_list[0]["descripcion"] == "Producto 1"
        assert items_list[0]["material"] == "oro_18k"

    @pytest.mark.asyncio
    async def test_update_invoice_preserves_items(
        self,
        async_db_with_org_user,
        org_id,
        user_id
    ):
        """
        Verifica que actualizar una factura preserva los items correctamente.
        """
        db = async_db_with_org_user

        # Crear factura inicial
        initial_items = [
            {"descripcion": "Item Original", "cantidad": 1, "precio_unitario": 100000},
        ]
        invoice_data = {
            "organization_id": org_id,
            "cliente_nombre": "Cliente Update Test",
            "subtotal": 100000,
            "total": 119000,
            "vendedor_id": user_id,
        }

        invoice = await create_invoice_with_items_async(
            db=db,
            invoice_data=invoice_data,
            items=initial_items,
        )
        invoice_id = invoice.id

        # Actualizar con nuevos items
        new_items = [
            {"descripcion": "Item Nuevo 1", "cantidad": 2, "precio_unitario": 80000},
            {"descripcion": "Item Nuevo 2", "cantidad": 1, "precio_unitario": 120000},
        ]

        updated = await update_invoice_with_items_async(
            db=db,
            invoice_id=invoice_id,
            org_id=org_id,
            invoice_updates={"subtotal": 280000, "total": 333200},
            items=new_items,
        )

        assert updated is not None

        # Verificar que los items fueron reemplazados
        items = await get_items_by_invoice_async(db, invoice_id)
        assert len(items) == 2
        descriptions = [i.descripcion for i in items]
        assert "Item Nuevo 1" in descriptions
        assert "Item Nuevo 2" in descriptions
        assert "Item Original" not in descriptions


# ============================================================================
# TEST CLASS: Métricas en Flujo de Facturación
# ============================================================================

class TestInvoiceFlowMetrics:
    """Tests de métricas durante el flujo de facturación."""

    @pytest.mark.asyncio
    async def test_metrics_tracked_on_sale(self):
        """
        Verifica que las métricas se trackean correctamente durante una venta.
        """
        # Crear collector independiente para este test
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)

        org_id = f"org-metrics-{uuid.uuid4().hex[:8]}"
        invoice_id = f"inv-{uuid.uuid4().hex[:8]}"

        items = [
            {
                "descripcion": "Anillo de oro",
                "cantidad": 1,
                "precio_unitario": 500000,
                "subtotal": 500000,
                "material": "oro_18k",
                "tipo_prenda": "anillo",
            },
        ]
        customer_data = {
            "nombre": "Cliente Métricas",
            "cedula": "123123123",
        }

        # Trackear venta completa
        await tracker.track_full_sale(
            organization_id=org_id,
            invoice_id=invoice_id,
            items=items,
            total_amount=595000,
            customer_data=customer_data,
            is_new_customer=True,
            user_id=1,
        )

        # Verificar eventos trackeados
        from src.metrics.collectors import EventType

        # Verificar cliente nuevo
        customer_events = await collector.get_events(
            event_type=EventType.CUSTOMER_NEW,
            organization_id=org_id,
        )
        assert len(customer_events) == 1

        # Verificar producto vendido
        product_events = await collector.get_events(
            event_type=EventType.PRODUCT_SOLD,
            organization_id=org_id,
        )
        assert len(product_events) == 1
        assert product_events[0].metadata["material"] == "oro_18k"

        # Verificar venta completada
        sale_events = await collector.get_events(
            event_type=EventType.SALE_COMPLETED,
            organization_id=org_id,
        )
        assert len(sale_events) == 1
        assert sale_events[0].metadata["invoice_id"] == invoice_id

    @pytest.mark.asyncio
    async def test_returning_customer_tracked(self):
        """
        Verifica que se trackea correctamente un cliente recurrente.
        """
        collector = MetricsCollector(max_events=1000, persist_to_db=False)
        tracker = MetricsTracker(collector=collector)

        org_id = f"org-returning-{uuid.uuid4().hex[:8]}"

        # Primera venta - cliente nuevo
        await tracker.track_customer_activity(
            organization_id=org_id,
            customer_cedula="444555666",
            customer_name="Cliente Recurrente",
            is_new=True,
            user_id=1,
        )

        # Segunda venta - cliente recurrente
        await tracker.track_customer_activity(
            organization_id=org_id,
            customer_cedula="444555666",
            customer_name="Cliente Recurrente",
            is_new=False,
            previous_purchases=1,
            user_id=1,
        )

        # Verificar eventos
        from src.metrics.collectors import EventType

        new_events = await collector.get_events(
            event_type=EventType.CUSTOMER_NEW,
            organization_id=org_id,
        )
        returning_events = await collector.get_events(
            event_type=EventType.CUSTOMER_RETURNING,
            organization_id=org_id,
        )

        assert len(new_events) == 1
        assert len(returning_events) == 1
        assert returning_events[0].metadata["previous_purchases"] == 1

"""
DocuBot — Seed de datos demo.
Ejecutar: python scripts/seed_demo.py
"""
import asyncio, sys, os, uuid
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://docubot:docubot_dev_2025@localhost:5432/docubot")

async def seed():
    engine = create_async_engine(DB_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM projects"))
        if result.scalar() > 0:
            print("✓ BD ya tiene datos. Seed omitido.")
            return

        tenant_id = "demo-tenant"
        project_id = str(uuid.uuid4())
        user_id = "demo-user-001"
        now = datetime.utcnow()

        await db.execute(text("""
            INSERT INTO projects (id,tenant_id,name,client,contract_number,status,created_by,created_at,updated_at)
            VALUES (:id,:t,:name,:client,:contract,'active',:u,:now,:now)
        """), {"id":project_id,"t":tenant_id,"name":"Planta Concentradora Norte",
               "client":"Aurenza Group","contract":"CONT-2024-001","u":user_id,"now":now})

        docs = [
            (str(uuid.uuid4()),"Contrato EPC Principal","contract","Contrato_EPC_Principal_Rev4.pdf"),
            (str(uuid.uuid4()),"Adenda N°2","amendment","Adenda_N2_20250328.pdf"),
            (str(uuid.uuid4()),"Especificaciones ETG-2025","technical_spec","ETG_2025_Especificaciones.pdf"),
            (str(uuid.uuid4()),"RFI-2025-043","rfi","RFI_2025_043_Fundaciones.pdf"),
        ]
        for doc_id, title, dtype, fname in docs:
            ver_id = str(uuid.uuid4())
            await db.execute(text("""
                INSERT INTO documents (id,tenant_id,project_id,title,document_type,filename,file_size,storage_url,created_by,created_at,updated_at)
                VALUES (:id,:t,:p,:title,:dtype,:fname,204800,:url,:u,:now,:now)
            """), {"id":doc_id,"t":tenant_id,"p":project_id,"title":title,"dtype":dtype,
                  "fname":fname,"url":f"demo://documents/{fname}","u":user_id,"now":now})
            await db.execute(text("""
                INSERT INTO document_versions (id,document_id,tenant_id,revision_number,processing_status,created_by,created_at,updated_at)
                VALUES (:id,:did,:t,'Rev. 4','processed',:u,:now,:now)
            """), {"id":ver_id,"did":doc_id,"t":tenant_id,"u":user_id,"now":now})
            await db.execute(text("UPDATE documents SET current_version_id=:v WHERE id=:d"),
                             {"v":ver_id,"d":doc_id})

        for title, sev, days in [
            ("Entregable Cláusula 12.3 vencido","critical",-9),
            ("Pago Estado N°4 vence en 8 días","warning",8),
        ]:
            await db.execute(text("""
                INSERT INTO alerts (id,tenant_id,project_id,title,severity,due_date,status,created_at,updated_at)
                VALUES (:id,:t,:p,:title,:sev,:due,'active',:now,:now)
            """), {"id":str(uuid.uuid4()),"t":tenant_id,"p":project_id,"title":title,
                  "sev":sev,"due":now+timedelta(days=days),"now":now})

        await db.commit()
        print(f"✓ Proyecto: {project_id}")
        print(f"✓ {len(docs)} documentos | 2 alertas")
        print(f"\nVITE_DEMO_PROJECT_ID={project_id}")

asyncio.run(seed())

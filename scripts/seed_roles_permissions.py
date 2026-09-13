"""
Roles, Permissions, and Initial System Administrator Seeding Script.
Populates standard RBAC matrix defined in SECURITY_MODEL.md.
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.auth import Permission, Role, RolePermission, User


# 1. System Roles definition
ROLES_DATA = [
    {
        "name": "investigator",
        "display_name": "Investigating Officer",
        "description": "Lead and investigating officers responsible for case investigation and evidence collection.",
        "is_system_role": True,
    },
    {
        "name": "forensic_expert",
        "display_name": "Forensic Expert / Analyst",
        "description": "Forensic lab personnel analyzing physical and digital evidence and generating reports.",
        "is_system_role": True,
    },
    {
        "name": "legal_officer",
        "display_name": "Legal Officer / Prosecutor",
        "description": "Public prosecutors and legal counsels preparing court filings and legal packages.",
        "is_system_role": True,
    },
    {
        "name": "supervisor",
        "display_name": "Supervisory Officer / SP",
        "description": "Superintendents of Police and division supervisors reviewing case milestones and audits.",
        "is_system_role": True,
    },
    {
        "name": "system_admin",
        "display_name": "System Administrator",
        "description": "Infrastructure, user management, and security monitoring administrators.",
        "is_system_role": True,
    },
]

# 2. Granular Permissions definition
PERMISSIONS_DATA = [
    # Cases
    ("cases", "create", "Create new legal investigation case"),
    ("cases", "read", "Read assigned case details and summary"),
    ("cases", "update", "Update case metadata and investigation status"),
    ("cases", "close", "Close or archive completed cases"),
    ("cases", "add_members", "Assign investigators and experts to a case team"),
    # Documents
    ("documents", "upload", "Upload new document files into case repository"),
    ("documents", "read", "Read and view document metadata"),
    ("documents", "download", "Download document file content"),
    ("documents", "version", "Create newer version of existing document"),
    # Evidence
    ("evidence", "register", "Register physical or digital evidence record"),
    ("evidence", "read", "View evidence metadata and integrity status"),
    ("evidence", "transfer", "Initiate custody transfer to another officer"),
    ("evidence", "receive", "Acknowledge and accept incoming evidence custody"),
    ("evidence", "verify", "Execute cryptographic SHA-256 integrity checks"),
    ("evidence", "download", "Download forensic digital evidence image/file"),
    # Custody
    ("custody", "view", "View chronological hash-chained chain of custody"),
    # Audit
    ("audit", "view_case", "View case-scoped audit log entries"),
    ("audit", "view_system", "View system-wide audit records"),
    # Search
    ("search", "traditional", "Execute structured filter search"),
    ("search", "semantic", "Execute natural language semantic vector search"),
    # AI
    ("ai", "ask", "Query AI RAG case assistant"),
    # Export
    ("export", "legal_package", "Generate court-ready document/evidence zip package"),
    # Users & Admin
    ("users", "create", "Register and provision new user accounts"),
    ("users", "read", "View user account profiles and status"),
    ("users", "update", "Update user account profile details"),
    ("users", "delete", "Deactivate or purge user accounts"),
    ("users", "status", "Activate, deactivate, or unlock user accounts"),
    ("users", "reset_password", "Perform administrative password reset"),
    ("roles", "manage", "Assign and modify system roles and permissions"),
    ("roles", "view", "Inspect system roles and permission matrices"),
    ("security", "view_events", "Inspect security alerts, brute force attempts, and tampering logs"),
    ("security", "resolve_alerts", "Mark security incident alerts as resolved"),
    ("system", "admin_panel", "Access privileged system administration interface"),
    ("system", "health", "Inspect internal infrastructure readiness diagnostics"),
]

# 3. Role-Permission Matrix Mapping
ROLE_PERMISSIONS_MAPPING = {
    "investigator": [
        ("cases", "create"), ("cases", "read"), ("cases", "update"), ("cases", "add_members"),
        ("documents", "upload"), ("documents", "read"), ("documents", "download"), ("documents", "version"),
        ("evidence", "register"), ("evidence", "read"), ("evidence", "transfer"), ("evidence", "receive"),
        ("evidence", "verify"), ("evidence", "download"),
        ("custody", "view"),
        ("audit", "view_case"),
        ("search", "traditional"), ("search", "semantic"),
        ("ai", "ask"),
    ],
    "forensic_expert": [
        ("cases", "read"),
        ("documents", "upload"), ("documents", "read"), ("documents", "download"), ("documents", "version"),
        ("evidence", "read"), ("evidence", "transfer"), ("evidence", "receive"), ("evidence", "verify"),
        ("evidence", "download"),
        ("custody", "view"),
        ("audit", "view_case"),
        ("search", "traditional"), ("search", "semantic"),
        ("ai", "ask"),
    ],
    "legal_officer": [
        ("cases", "read"),
        ("documents", "upload"), ("documents", "read"), ("documents", "download"), ("documents", "version"),
        ("evidence", "read"), ("evidence", "receive"), ("evidence", "verify"), ("evidence", "download"),
        ("custody", "view"),
        ("audit", "view_case"),
        ("search", "traditional"), ("search", "semantic"),
        ("ai", "ask"),
        ("export", "legal_package"),
    ],
    "supervisor": [
        ("cases", "create"), ("cases", "read"), ("cases", "update"), ("cases", "close"), ("cases", "add_members"),
        ("documents", "upload"), ("documents", "read"), ("documents", "download"), ("documents", "version"),
        ("evidence", "register"), ("evidence", "read"), ("evidence", "transfer"), ("evidence", "receive"),
        ("evidence", "verify"), ("evidence", "download"),
        ("custody", "view"),
        ("audit", "view_case"),
        ("search", "traditional"), ("search", "semantic"),
        ("ai", "ask"),
        ("export", "legal_package"),
        ("security", "view_events"),
    ],
    "system_admin": [
        ("users", "create"), ("users", "read"), ("users", "update"), ("users", "delete"),
        ("users", "status"), ("users", "reset_password"),
        ("roles", "manage"), ("roles", "view"),
        ("audit", "view_system"),
        ("security", "view_events"), ("security", "resolve_alerts"),
        ("system", "admin_panel"), ("system", "health"),
    ],
}


async def seed_database():
    print("=== [SIH-190] Seeding Roles & Permissions ===")
    async with AsyncSessionLocal() as session:
        # A. Seed Roles
        role_objs = {}
        for r_data in ROLES_DATA:
            res = await session.execute(select(Role).where(Role.name == r_data["name"]))
            existing = res.scalar_one_or_none()
            if not existing:
                role = Role(
                    name=r_data["name"],
                    display_name=r_data["display_name"],
                    description=r_data["description"],
                    is_system_role=r_data["is_system_role"],
                )
                session.add(role)
                await session.flush()
                role_objs[r_data["name"]] = role
                print(f"  ✓ Created Role: {r_data['name']}")
            else:
                role_objs[r_data["name"]] = existing
                print(f"  - Role exists: {r_data['name']}")

        # B. Seed Permissions
        perm_objs = {}
        for res_name, act_name, desc in PERMISSIONS_DATA:
            q = select(Permission).where(Permission.resource == res_name, Permission.action == act_name)
            res = await session.execute(q)
            existing = res.scalar_one_or_none()
            key = (res_name, act_name)
            if not existing:
                perm = Permission(resource=res_name, action=act_name, description=desc)
                session.add(perm)
                await session.flush()
                perm_objs[key] = perm
            else:
                perm_objs[key] = existing
        print(f"  ✓ Seeded {len(PERMISSIONS_DATA)} system permissions")

        # C. Map Role Permissions
        total_mappings = 0
        for role_name, perms in ROLE_PERMISSIONS_MAPPING.items():
            role = role_objs[role_name]
            for p_key in perms:
                perm = perm_objs[p_key]
                link_q = select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id
                )
                link_res = await session.execute(link_q)
                if not link_res.scalar_one_or_none():
                    link = RolePermission(role_id=role.id, permission_id=perm.id)
                    session.add(link)
                    total_mappings += 1
        await session.flush()
        print(f"  ✓ Added {total_mappings} role-permission mappings")

        # D. Seed Initial System Administrator (Development Account)
        admin_email = "admin@ncrb.gov.in"
        user_q = select(User).where(User.email == admin_email)
        admin_res = await session.execute(user_q)
        admin_user = admin_res.scalar_one_or_none()

        if not admin_user:
            admin_user = User(
                employee_id="EMP-ADMIN-001",
                email=admin_email,
                full_name="DOCSHIELD System Administrator",
                password_hash=hash_password("Admin@DocShield2026!"),
                role_id=role_objs["system_admin"].id,
                department="Information Technology & Cyber Security",
                designation="Chief System Security Officer",
                is_active=True,
                is_locked=False,
            )
            session.add(admin_user)
            await session.flush()
            print(f"  ✓ Created System Admin: {admin_email} (EMP-ADMIN-001)")
        else:
            print(f"  - System Admin exists: {admin_email}")

        # E. Seed Sample Investigator (Development Account)
        inv_email = "officer@ncrb.gov.in"
        inv_q = select(User).where(User.email == inv_email)
        inv_res = await session.execute(inv_q)
        inv_user = inv_res.scalar_one_or_none()

        if not inv_user:
            inv_user = User(
                employee_id="EMP-INV-001",
                email=inv_email,
                full_name="Inspector Rajesh Sharma",
                password_hash=hash_password("Investigator@2026!"),
                role_id=role_objs["investigator"].id,
                department="Cybercrime Investigation Division",
                designation="Senior Inspector",
                is_active=True,
                is_locked=False,
            )
            session.add(inv_user)
            await session.flush()
            print(f"  ✓ Created Sample Investigator: {inv_email} (EMP-INV-001)")
        else:
            print(f"  - Sample Investigator exists: {inv_email}")

        # F. Seed Sample Supervisor
        sup_email = "supervisor@ncrb.gov.in"
        sup_q = select(User).where(User.email == sup_email)
        sup_res = await session.execute(sup_q)
        sup_user = sup_res.scalar_one_or_none()
        if not sup_user:
            sup_user = User(
                employee_id="EMP-SUP-001",
                email=sup_email,
                full_name="SP Anita Deshmukh",
                password_hash=hash_password("Supervisor@2026!"),
                role_id=role_objs["supervisor"].id,
                department="Supervisory Oversight Division",
                designation="Superintendent of Police",
                is_active=True,
                is_locked=False,
            )
            session.add(sup_user)
            await session.flush()
            print(f"  ✓ Created Sample Supervisor: {sup_email} (EMP-SUP-001)")
        else:
            print(f"  - Sample Supervisor exists: {sup_email}")

        # G. Seed Sample Forensic Expert
        for_email = "forensic@ncrb.gov.in"
        for_q = select(User).where(User.email == for_email)
        for_res = await session.execute(for_q)
        for_user = for_res.scalar_one_or_none()
        if not for_user:
            for_user = User(
                employee_id="EMP-FOR-001",
                email=for_email,
                full_name="Dr. Vikram Sen",
                password_hash=hash_password("Forensic@2026!"),
                role_id=role_objs["forensic_expert"].id,
                department="Central Forensic Science Laboratory",
                designation="Senior Scientific Officer",
                is_active=True,
                is_locked=False,
            )
            session.add(for_user)
            await session.flush()
            print(f"  ✓ Created Sample Forensic Expert: {for_email} (EMP-FOR-001)")
        else:
            print(f"  - Sample Forensic Expert exists: {for_email}")

        # H. Seed Sample Legal Officer
        leg_email = "legal@ncrb.gov.in"
        leg_q = select(User).where(User.email == leg_email)
        leg_res = await session.execute(leg_q)
        leg_user = leg_res.scalar_one_or_none()
        if not leg_user:
            leg_user = User(
                employee_id="EMP-LEG-001",
                email=leg_email,
                full_name="Advocate Priya Rao",
                password_hash=hash_password("Legal@2026!"),
                role_id=role_objs["legal_officer"].id,
                department="Directorate of Prosecution",
                designation="Public Prosecutor",
                is_active=True,
                is_locked=False,
            )
            session.add(leg_user)
            await session.flush()
            print(f"  ✓ Created Sample Legal Officer: {leg_email} (EMP-LEG-001)")
        else:
            print(f"  - Sample Legal Officer exists: {leg_email}")

        await session.commit()
    print("=== Roles, Permissions, and Initial Accounts Seeded Successfully ===")


if __name__ == "__main__":
    asyncio.run(seed_database())

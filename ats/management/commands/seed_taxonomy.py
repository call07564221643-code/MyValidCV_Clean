from django.core.management.base import BaseCommand

from ats.models import (
    JobFamily,
    Qualification,
    RoleTemplate,
    RoleTemplateQualification,
    RoleTemplateSkill,
    Skill,
)


FAMILIES = {
    "Administration": "Office, records, scheduling, reception and operational support roles.",
    "Technology": "Software, data, infrastructure, QA and technical support roles.",
    "Finance": "Accounting, bookkeeping, payroll, audit and financial analysis roles.",
    "Healthcare": "Clinical, care, dental, pharmacy and patient-facing healthcare roles.",
    "Human Resources": "Recruitment, employee relations, HR operations and learning roles.",
    "Sales and Marketing": "Sales, account management, marketing, CRM and growth roles.",
    "Logistics": "Warehouse, transport, supply chain, aviation and operations roles.",
    "Education": "Teaching, training, learner support and academic administration roles.",
    "Hospitality": "Customer-facing hospitality, food service, events and hotel roles.",
}


SKILLS = [
    ("Administration", "domain", "admin,office administration"),
    ("Scheduling", "process", "diary management,rota planning,appointment booking"),
    ("Records Management", "process", "filing,document control"),
    ("Data Entry", "process", "accurate data input"),
    ("Customer Service", "soft", "client service,customer support"),
    ("Reception", "domain", "front desk"),
    ("Compliance", "process", "regulatory compliance"),
    ("Excel", "tool", "microsoft excel,spreadsheets"),
    ("Python", "technical", ""),
    ("Django", "technical", ""),
    ("SQL", "technical", "database queries"),
    ("PostgreSQL", "technical", "postgres"),
    ("API Development", "technical", "rest api,apis"),
    ("Git", "tool", "github,version control"),
    ("Testing", "process", "qa,quality assurance"),
    ("Docker", "tool", "containers"),
    ("AWS", "tool", "amazon web services"),
    ("Windows", "tool", "microsoft windows"),
    ("Data Analysis", "technical", "analytics,reporting"),
    ("Power BI", "tool", "powerbi"),
    ("Bookkeeping", "domain", "accounts processing"),
    ("Payroll", "domain", "payroll processing"),
    ("Budgeting", "domain", "forecasting"),
    ("Reconciliations", "domain", "bank reconciliation"),
    ("VAT Returns", "domain", "vat"),
    ("Patient Care", "domain", "care planning"),
    ("Clinical Assessment", "domain", "assessment"),
    ("Infection Control", "domain", "cross infection"),
    ("Radiography", "domain", "x-ray,xray"),
    ("Treatment Planning", "domain", "care plan"),
    ("Recruitment", "domain", "talent acquisition,hiring"),
    ("Employee Relations", "domain", "er cases"),
    ("Onboarding", "process", "induction"),
    ("CRM", "tool", "salesforce,hubspot"),
    ("Lead Generation", "domain", "prospecting"),
    ("Campaign Management", "domain", "marketing campaigns"),
    ("Warehouse Operations", "domain", "warehouse"),
    ("Inventory Control", "domain", "stock control"),
    ("Forklift Operation", "domain", "forklift"),
    ("Passenger Service", "domain", "airport passenger service"),
    ("Lesson Planning", "domain", "curriculum planning"),
    ("Safeguarding", "process", "child protection"),
    ("Food Safety", "process", "haccp"),
    ("POS Systems", "tool", "point of sale,till systems"),
    ("Communication", "soft", "written communication,verbal communication"),
    ("Leadership", "soft", "team leadership"),
    ("Problem Solving", "soft", "troubleshooting"),
    ("Project Management", "process", "delivery management"),
]


QUALIFICATIONS = [
    ("GCSE Maths and English", "education", "", False, "gcse"),
    ("Business Administration Diploma", "education", "", False, "admin diploma"),
    ("Computer Science Degree", "education", "", False, "cs degree"),
    ("ACCA", "certification", "ACCA", False, "chartered certified accountant"),
    ("AAT", "certification", "AAT", False, "association of accounting technicians"),
    ("GDC Registration", "licence", "General Dental Council", True, "gdc,dental registration"),
    ("Dental Nursing Diploma", "education", "", False, "dental nurse diploma"),
    ("NMC PIN", "licence", "Nursing and Midwifery Council", True, "nursing pin"),
    ("CIPD", "certification", "CIPD", False, "hr certification"),
    ("Forklift Licence", "licence", "", True, "counterbalance licence,flt licence"),
    ("Teaching Qualification", "education", "", False, "pgce,qts"),
    ("Food Hygiene Certificate", "certification", "", False, "food safety certificate"),
    ("PMP", "certification", "PMI", False, "project management professional"),
    ("AWS Certification", "certification", "Amazon Web Services", False, "aws certified"),
]


ROLES = [
    ("Administration", "Office Administrator", "mid", "administrator,admin assistant,office assistant", ["Administration", "Scheduling", "Records Management", "Data Entry", "Customer Service", "Excel", "Communication"], ["Business Administration Diploma"]),
    ("Administration", "Receptionist", "entry", "front desk receptionist", ["Reception", "Scheduling", "Customer Service", "Data Entry", "Communication"], ["GCSE Maths and English"]),
    ("Technology", "Django Developer", "mid", "python developer,backend developer", ["Python", "Django", "SQL", "PostgreSQL", "API Development", "Git", "Testing"], ["Computer Science Degree"]),
    ("Technology", "IT Support Analyst", "junior", "helpdesk analyst,technical support", ["Customer Service", "Problem Solving", "Testing", "Communication", "Windows"], []),
    ("Technology", "DevOps Engineer", "senior", "cloud engineer,platform engineer", ["AWS", "Docker", "Git", "Testing", "Problem Solving"], ["AWS Certification"]),
    ("Finance", "Management Accountant", "mid", "accountant,finance analyst", ["Bookkeeping", "Payroll", "Budgeting", "Reconciliations", "VAT Returns", "Excel", "Data Analysis"], ["ACCA", "AAT"]),
    ("Finance", "Payroll Officer", "mid", "payroll administrator", ["Payroll", "Excel", "Compliance", "Data Entry", "Communication"], ["AAT"]),
    ("Healthcare", "Dentist", "senior", "dental surgeon", ["Patient Care", "Clinical Assessment", "Infection Control", "Radiography", "Treatment Planning", "Communication"], ["GDC Registration"]),
    ("Healthcare", "Dental Nurse", "mid", "trainee dental nurse", ["Patient Care", "Infection Control", "Radiography", "Scheduling", "Communication"], ["GDC Registration", "Dental Nursing Diploma"]),
    ("Human Resources", "HR Coordinator", "mid", "hr assistant,people coordinator", ["Recruitment", "Onboarding", "Employee Relations", "Records Management", "Communication"], ["CIPD"]),
    ("Sales and Marketing", "Sales Executive", "mid", "account executive", ["CRM", "Lead Generation", "Customer Service", "Communication", "Data Analysis"], []),
    ("Sales and Marketing", "Marketing Specialist", "mid", "marketing executive", ["Campaign Management", "CRM", "Data Analysis", "Communication", "Project Management"], []),
    ("Logistics", "Warehouse Operative", "entry", "warehouse assistant", ["Warehouse Operations", "Inventory Control", "Forklift Operation", "Compliance", "Communication"], ["Forklift Licence"]),
    ("Logistics", "Airport Administrator", "mid", "airport admin,aviation administrator", ["Administration", "Passenger Service", "Scheduling", "Records Management", "Compliance", "Data Entry"], []),
    ("Education", "Teaching Assistant", "entry", "learning support assistant", ["Safeguarding", "Lesson Planning", "Communication", "Customer Service"], ["GCSE Maths and English"]),
    ("Education", "Teacher", "mid", "class teacher", ["Lesson Planning", "Safeguarding", "Communication", "Leadership"], ["Teaching Qualification"]),
    ("Hospitality", "Restaurant Supervisor", "mid", "hospitality supervisor", ["Customer Service", "Food Safety", "POS Systems", "Leadership", "Scheduling"], ["Food Hygiene Certificate"]),
]


class Command(BaseCommand):
    help = "Seed reusable ATS job families, skills, qualifications and role templates."

    def handle(self, *args, **options):
        families = self.seed_families()
        skills = self.seed_skills()
        qualifications = self.seed_qualifications()
        role_count = self.seed_roles(families, skills, qualifications)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded taxonomy: {len(families)} families, {len(skills)} skills, "
                f"{len(qualifications)} qualifications, {role_count} role templates."
            )
        )

    def seed_families(self):
        records = {}
        for name, description in FAMILIES.items():
            family, _created = JobFamily.objects.update_or_create(
                name=name,
                defaults={"description": description},
            )
            records[name] = family
        return records

    def seed_skills(self):
        records = {}
        for name, category, aliases in SKILLS:
            skill, _created = Skill.objects.update_or_create(
                normalized_name=name.lower(),
                defaults={"name": name, "category": category, "aliases": aliases},
            )
            records[name] = skill
        return records

    def seed_qualifications(self):
        records = {}
        for name, category, issuing_body, is_license, aliases in QUALIFICATIONS:
            qualification, _created = Qualification.objects.update_or_create(
                normalized_name=name.lower(),
                defaults={
                    "name": name,
                    "category": category,
                    "issuing_body": issuing_body,
                    "is_license": is_license,
                    "aliases": aliases,
                },
            )
            records[name] = qualification
        return records

    def seed_roles(self, families, skills, qualifications):
        count = 0
        for family_name, title, seniority, aliases, skill_names, qualification_names in ROLES:
            role, _created = RoleTemplate.objects.update_or_create(
                job_family=families[family_name],
                normalized_title=title.lower(),
                seniority_level=seniority,
                defaults={"title": title, "aliases": aliases},
            )
            count += 1
            for index, skill_name in enumerate(skill_names):
                importance = "required" if index < 4 else "preferred"
                RoleTemplateSkill.objects.update_or_create(
                    role_template=role,
                    skill=skills[skill_name],
                    defaults={"importance": importance},
                )
            for qualification_name in qualification_names:
                qualification = qualifications[qualification_name]
                RoleTemplateQualification.objects.update_or_create(
                    role_template=role,
                    qualification=qualification,
                    defaults={"importance": "required" if qualification.is_license else "preferred"},
                )
        return count

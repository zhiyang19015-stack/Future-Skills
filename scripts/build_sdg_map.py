"""Write data/sdg_map.csv: the UN Sustainable Development Goal targets each occupation and skill serves.

Each link is ours, with a written reason, at the most general level it holds for:

    field       a SOC major group (data/fields.csv): every occupation in it
    minor       a SOC minor group ("25-1": postsecondary teachers)
    broad       a SOC detailed occupation ("17-2051": civil engineers, with its O*NET variants)
    occupation  one O*NET occupation ("11-3051.02")
    element     a skill or knowledge area (data/elements.csv)

An occupation takes the links of its most specific level that has any: a rule for civil
engineers replaces the field's rule for them rather than adding to it, so every link shown was
written for that occupation. "direct" means the work itself is what the target asks for (nurses
and target 3.c, the health workforce); "indirect" that the work supports it.

Every entity is checked against the data; an unknown code stops the script.

Usage: python scripts/build_sdg_map.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = {"source_name": "UN Global indicator framework for the SDGs and targets of the 2030 Agenda "
                         "(A/RES/71/313 Annex, as refined to 2026); links and reasons ours",
          "source_url": "https://unstats.un.org/sdgs/indicators/indicators-list/",
          "source_date": date.today().isoformat()}
GOALS = {1: "No Poverty", 2: "Zero Hunger", 3: "Good Health and Well-being", 4: "Quality Education",
         5: "Gender Equality", 6: "Clean Water and Sanitation", 7: "Affordable and Clean Energy",
         8: "Decent Work and Economic Growth", 9: "Industry, Innovation and Infrastructure",
         10: "Reduced Inequalities", 11: "Sustainable Cities and Communities",
         12: "Responsible Consumption and Production", 13: "Climate Action", 14: "Life Below Water",
         15: "Life on Land", 16: "Peace, Justice and Strong Institutions", 17: "Partnerships for the Goals"}

D, I = "direct", "indirect"
# (level, code, target, strength, reason)
RULES = [
    # --- fields -----------------------------------------------------------------------------------
    ("field", "11", "8.2", I, "Managers decide how an organisation uses its people and tools, which sets how productive it is."),
    ("field", "13", "8.10", I, "Accounting, finance and business staff keep companies and financial services sound and open to people."),
    ("field", "15", "9.c", I, "Computer and data work builds and runs the digital services people reach through ICT."),
    ("field", "15", "9.5", I, "Software, data and analysis work raises the technological capability of industry."),
    ("field", "17", "9.4", I, "Engineers and technicians design the infrastructure and industrial upgrades the target asks for."),
    ("field", "19", "9.5", D, "Scientists carry out the research the target asks countries to strengthen."),
    ("field", "21", "10.2", D, "Social and community workers help people take part in social and economic life."),
    ("field", "23", "16.3", D, "Legal work is how the rule of law and equal access to justice reach people."),
    ("field", "25", "4.c", D, "Teachers, trainers and library staff are the qualified education workforce the target asks for."),
    ("field", "27", "11.4", I, "Artists, designers and media workers keep culture alive and visible."),
    ("field", "29", "3.8", D, "Health practitioners deliver the health services universal health coverage depends on."),
    ("field", "29", "3.c", D, "They are the health workforce the target asks countries to train and keep."),
    ("field", "31", "3.c", D, "Health support workers are part of the health workforce the target asks countries to grow."),
    ("field", "33", "16.1", D, "Police, security and corrections work reduces violence and keeps people safe."),
    ("field", "35", "2.1", I, "Cooks and food service workers prepare safe food for people every day."),
    ("field", "37", "6.2", I, "Cleaning and building upkeep provide the sanitation and hygiene people need."),
    ("field", "39", "8.5", I, "Personal service jobs are a large share of employment, so decent work in them matters."),
    ("field", "41", "8.3", I, "Sales work keeps small and medium businesses trading."),
    ("field", "43", "8.2", I, "Office and administrative work keeps organisations running productively."),
    ("field", "45", "2.3", D, "Farm, fishing and forestry workers produce food and raise rural incomes."),
    ("field", "47", "9.1", I, "Construction workers build the roads, buildings and utilities infrastructure is made of."),
    ("field", "49", "12.5", I, "Maintenance and repair keep machines and products in use longer, which cuts waste."),
    ("field", "51", "9.2", I, "Production work is the core of industrialisation that creates jobs."),
    ("field", "53", "11.2", I, "Drivers and transport workers move people and goods; safe, reliable transport depends on them."),
    # --- management -------------------------------------------------------------------------------
    ("broad", "11-9031", "4.2", D, "Education and childcare administrators run early-childhood and school programmes."),
    ("broad", "11-9032", "4.1", D, "School administrators run the primary and secondary schools the target is about."),
    ("broad", "11-9033", "4.3", D, "Postsecondary administrators run the colleges and universities that give access to tertiary education."),
    ("occupation", "11-3051.02", "7.2", D, "Geothermal plants produce renewable energy."),
    ("occupation", "11-3051.03", "7.2", D, "Biofuel production adds renewable energy."),
    ("occupation", "11-3051.04", "7.2", D, "Biomass power plants produce renewable energy."),
    ("occupation", "11-3051.06", "7.2", D, "Hydroelectric plants produce renewable energy."),
    ("broad", "11-9013", "2.3", D, "Farm managers raise agricultural productivity and the income farms bring."),
    ("broad", "11-9111", "3.8", I, "Health services managers run the clinics and hospitals people get care from."),
    ("broad", "11-9121", "9.5", I, "Science managers direct research programmes."),
    # --- business and finance ------------------------------------------------------------------
    ("broad", "13-2081", "16.6", D, "Tax examiners and collectors make public revenue accountable and fair."),
    ("broad", "13-2011", "16.6", I, "Accountants and auditors make organisations' finances transparent and accountable."),
    ("occupation", "13-1041.00", "16.5", I, "Compliance officers check that organisations follow the law, which limits corruption."),
    ("occupation", "13-1041.01", "12.4", D, "Environmental compliance inspectors check how chemicals and waste are handled."),
    ("occupation", "13-1041.03", "10.2", D, "Equal opportunity officers protect people from discrimination at work."),
    ("broad", "13-2052", "8.10", D, "Financial advisers open financial services to more people."),
    # --- engineering and architecture ----------------------------------------------------------
    ("broad", "17-2051", "9.1", D, "Civil engineers design roads, bridges, water systems and other infrastructure."),
    ("occupation", "17-2051.02", "6.3", D, "Water and wastewater engineers improve water quality and treatment."),
    ("broad", "17-2081", "6.3", D, "Environmental engineers design systems that clean water, air and land."),
    ("occupation", "17-2199.10", "7.2", D, "Wind energy engineers design renewable power plants."),
    ("occupation", "17-2199.11", "7.2", D, "Solar energy engineers design renewable power systems."),
    ("occupation", "17-2199.03", "7.3", D, "Energy engineers improve how efficiently buildings and plants use energy."),
    ("broad", "17-1011", "11.1", I, "Architects design housing and buildings that are safe to live and work in."),
    ("broad", "17-1012", "11.7", D, "Landscape architects design green and public spaces."),
    ("broad", "17-2041", "12.4", I, "Chemical engineers design processes that handle chemicals and waste safely."),
    ("broad", "17-2071", "7.1", I, "Electrical engineers design the systems that bring reliable power to homes and industry."),
    ("broad", "17-3025", "6.3", I, "Environmental engineering technicians run the tests and equipment that keep water clean."),
    ("broad", "17-2111", "8.8", D, "Health and safety engineers make workplaces safe."),
    ("broad", "17-2021", "2.4", I, "Agricultural engineers design machines and systems for sustainable farming."),
    # --- science -----------------------------------------------------------------------------------
    ("broad", "19-1011", "2.4", D, "Animal scientists improve sustainable livestock production."),
    ("broad", "19-1012", "2.1", I, "Food scientists make food safer and more nutritious."),
    ("broad", "19-1013", "2.4", D, "Soil and plant scientists make crop production more sustainable."),
    ("broad", "19-1031", "15.1", D, "Conservation scientists protect land and freshwater ecosystems."),
    ("broad", "19-1032", "15.2", D, "Foresters manage forests sustainably."),
    ("broad", "19-1023", "15.5", D, "Wildlife biologists study and protect threatened species."),
    ("broad", "19-1041", "3.d", D, "Epidemiologists give early warning of disease outbreaks and health risks."),
    ("broad", "19-1042", "3.b", D, "Medical scientists research new medicines and vaccines."),
    ("occupation", "19-2041.00", "11.6", D, "Environmental scientists measure and reduce pollution and waste."),
    ("occupation", "19-2041.01", "13.2", D, "Climate change policy analysts help build climate measures into policy."),
    ("occupation", "19-2041.02", "15.3", D, "Environmental restoration planners restore degraded land."),
    ("occupation", "19-2041.03", "12.2", D, "Industrial ecologists make industry use natural resources efficiently."),
    ("broad", "19-2043", "6.5", D, "Hydrologists study water resources so they can be managed sustainably."),
    ("occupation", "19-3011.01", "12.2", I, "Environmental economists put a value on natural resources and their use."),
    ("broad", "19-3033", "3.4", D, "Clinical and counselling psychologists treat mental illness and promote mental health."),
    ("broad", "19-3051", "11.3", D, "Urban and regional planners plan inclusive, sustainable towns and cities."),
    ("broad", "19-4042", "6.3", I, "Environmental science technicians test water, air and soil for pollution."),
    ("broad", "19-4012", "2.4", I, "Agricultural technicians support sustainable crop and livestock production."),
    ("broad", "19-5011", "8.8", D, "Occupational health and safety specialists make workplaces safe."),
    # --- community and social service -------------------------------------------------------------
    ("broad", "21-1011", "3.5", D, "Substance abuse counsellors treat and help prevent drug and alcohol misuse."),
    ("broad", "21-1012", "4.4", I, "Career and guidance counsellors help people choose the skills and studies that lead to work."),
    ("broad", "21-1013", "3.4", D, "Family therapists promote mental health and well-being."),
    ("broad", "21-1014", "3.4", D, "Mental health counsellors treat mental illness and promote well-being."),
    ("broad", "21-1021", "16.2", D, "Child and family social workers protect children from abuse and neglect."),
    ("broad", "21-1022", "3.8", I, "Healthcare social workers help patients get and keep the care they need."),
    ("broad", "21-1091", "3.4", I, "Health educators help people prevent illness and live healthily."),
    ("broad", "21-1094", "3.8", D, "Community health workers bring basic health services to the people who need them."),
    # --- legal ---------------------------------------------------------------------------------------
    ("broad", "23-1023", "16.3", D, "Judges decide cases under the rule of law."),
    # --- education ----------------------------------------------------------------------------------
    ("broad", "25-2011", "4.2", D, "Preschool teachers give children the early education the target asks for."),
    ("broad", "25-2012", "4.2", D, "Kindergarten teachers give children the early education the target asks for."),
    ("broad", "25-2021", "4.1", D, "Primary school teachers give children the quality schooling the target asks for."),
    ("broad", "25-2031", "4.1", D, "Secondary school teachers give young people the quality schooling the target asks for."),
    ("broad", "25-2051", "4.5", D, "Special education teachers give children with disabilities equal access to education."),
    ("broad", "25-2057", "4.5", D, "Special education teachers give children with disabilities equal access to education."),
    ("minor", "25-1", "4.3", D, "Lecturers and college teachers provide the tertiary education the target asks for."),
    ("broad", "25-3011", "4.6", D, "Adult literacy teachers help adults learn to read, write and count."),
    ("broad", "25-4022", "16.10", D, "Librarians give the public access to information."),
    ("broad", "25-4011", "11.4", D, "Archivists safeguard documentary heritage."),
    ("broad", "25-4012", "11.4", D, "Curators safeguard cultural and natural heritage."),
    # --- arts and media ----------------------------------------------------------------------------
    ("broad", "27-3023", "16.10", D, "Journalists give the public access to information."),
    ("broad", "27-3041", "16.10", I, "Editors check and publish the information the public reads."),
    # --- health ---------------------------------------------------------------------------------------
    ("broad", "29-1131", "2.4", I, "Vets keep farm animals healthy, which food production depends on."),
    ("broad", "29-1031", "2.2", D, "Dietitians and nutritionists treat and prevent malnutrition."),
    ("broad", "31-1121", "3.8", I, "Home health aides bring care to people in their own homes."),
    ("broad", "31-1122", "3.8", I, "Personal care aides help older and disabled people with daily care."),
    # --- protective, food, cleaning, personal care --------------------------------------------------
    ("broad", "33-2011", "11.5", D, "Firefighters reduce the deaths and losses that fires and disasters cause."),
    ("broad", "37-2021", "3.3", I, "Pest control helps stop diseases such as dengue that insects and rats spread."),
    ("broad", "37-3011", "11.7", I, "Landscaping and grounds work keeps parks and public spaces green and usable."),
    ("broad", "39-9011", "4.2", D, "Childcare workers give young children early care and development."),
    ("broad", "39-9031", "3.4", I, "Fitness trainers help people stay active, which prevents illness."),
    ("broad", "39-7011", "8.9", D, "Tour guides are part of the sustainable tourism that creates jobs and promotes local culture."),
    ("broad", "39-7012", "8.9", D, "Travel guides are part of the sustainable tourism that creates jobs and promotes local culture."),
    # --- sales and office ---------------------------------------------------------------------------
    ("broad", "41-9021", "11.1", I, "Real estate brokers help people find housing."),
    ("broad", "41-9022", "11.1", I, "Real estate agents help people find housing."),
    ("broad", "41-3021", "8.10", D, "Insurance agents open insurance services to more people."),
    ("broad", "41-3031", "8.10", D, "Financial services sales agents open financial services to more people."),
    ("broad", "43-3071", "8.10", D, "Bank tellers give people access to banking."),
    ("broad", "43-4061", "1.3", D, "Eligibility interviewers connect people to social protection programmes."),
    # --- farming, fishing, forestry -----------------------------------------------------------------
    ("broad", "45-2011", "2.4", I, "Agricultural inspectors check that food is produced safely."),
    ("broad", "45-3031", "14.4", D, "Fishing workers' practices decide whether fish stocks are harvested sustainably."),
    ("broad", "45-4011", "15.2", D, "Forest and conservation workers manage and replant forests."),
    ("broad", "45-4021", "15.2", I, "Fallers' work decides whether logging keeps forests sustainable."),
    ("broad", "45-4022", "15.2", I, "Logging machine operators' work decides whether logging keeps forests sustainable."),
    # --- construction, repair, production, transport --------------------------------------------------
    ("broad", "47-2231", "7.2", D, "Solar panel installers add renewable energy."),
    ("occupation", "47-2152.04", "7.2", D, "Solar thermal installers add renewable energy."),
    ("broad", "47-2111", "7.1", I, "Electricians bring safe, reliable power into homes and workplaces."),
    ("occupation", "47-2152.00", "6.1", I, "Plumbers install and repair the pipes that bring safe water."),
    ("minor", "47-5", "12.2", I, "Extraction work decides how efficiently natural resources are used."),
    ("broad", "49-9081", "7.2", D, "Wind turbine technicians keep renewable power plants running."),
    ("broad", "49-9021", "7.3", I, "Air-conditioning and refrigeration mechanics keep cooling systems energy-efficient."),
    ("broad", "51-8031", "6.3", D, "Water and wastewater plant operators treat the water people use and return to rivers."),
    ("broad", "51-8013", "7.1", I, "Power plant operators keep electricity flowing."),
    ("occupation", "51-8013.03", "7.2", D, "Biomass plant technicians produce renewable energy."),
    ("occupation", "51-8013.04", "7.2", D, "Hydroelectric plant technicians produce renewable energy."),
    ("broad", "51-8091", "12.4", I, "Chemical plant operators handle chemicals and their waste."),
    ("minor", "51-3", "12.3", I, "Food processing workers decide how much food is lost along the production chain."),
    ("broad", "53-3052", "11.2", D, "Bus drivers run the public transport the target asks to expand."),
    ("broad", "53-7081", "11.6", D, "Refuse and recycling collectors manage city waste."),
    # --- skills and knowledge -------------------------------------------------------------------------
    ("element", "2.C.1.a", "8.2", I, "Knowing how to manage an organisation raises its productivity."),
    ("element", "2.C.1.c", "8.10", I, "Economics and accounting keep businesses and financial services sound."),
    ("element", "2.C.1.d", "8.3", I, "Sales and marketing keep small businesses growing."),
    ("element", "2.C.1.f", "8.5", I, "Human resources knowledge covers fair hiring, pay and conditions at work."),
    ("element", "2.C.2.a", "9.2", I, "Production knowledge is the base of manufacturing jobs."),
    ("element", "2.C.2.b", "2.4", D, "Knowing how food is grown and produced is what sustainable food production needs."),
    ("element", "2.C.3.a", "9.c", I, "Computer and electronics knowledge builds and runs digital services."),
    ("element", "2.C.3.b", "9.4", I, "Engineering knowledge is needed to upgrade infrastructure and industry."),
    ("element", "2.C.3.c", "9.1", I, "Design and drawing knowledge turns plans for infrastructure into buildable designs."),
    ("element", "2.C.3.d", "11.1", I, "Building and construction knowledge is needed for safe housing."),
    ("element", "2.C.3.e", "9.4", I, "Mechanical knowledge keeps machines and industry running efficiently."),
    ("element", "2.C.4.a", "4.6", I, "Mathematics builds the numeracy the target asks for."),
    ("element", "2.C.4.b", "9.5", I, "Physics underlies research and new technology."),
    ("element", "2.C.4.c", "12.4", I, "Chemistry is needed to handle chemicals and waste safely."),
    ("element", "2.C.4.d", "15.1", I, "Biology is needed to protect living things and ecosystems."),
    ("element", "2.C.4.e", "3.4", I, "Psychology is needed to support mental health."),
    ("element", "2.C.4.f", "10.2", I, "Sociology helps understand and include every group in society."),
    ("element", "2.C.4.g", "11.3", I, "Geography is needed to plan towns, land and resources."),
    ("element", "2.C.5.a", "3.8", D, "Medical and dental knowledge is what health services are built on."),
    ("element", "2.C.5.b", "3.4", D, "Therapy and counselling knowledge treats mental and physical conditions."),
    ("element", "2.C.6", "4.c", D, "Knowing how to teach and train is what qualified teachers need."),
    ("element", "2.C.7.a", "4.6", I, "Language knowledge builds the literacy the target asks for."),
    ("element", "2.C.7.b", "4.4", I, "A second language widens the work a person can do."),
    ("element", "2.C.7.c", "11.4", I, "Arts knowledge keeps cultural heritage alive."),
    ("element", "2.C.7.d", "11.4", D, "History and archaeology study and protect cultural heritage."),
    ("element", "2.C.7.e", "4.7", I, "Philosophy and religion teach the values of peace and global citizenship."),
    ("element", "2.C.8.a", "16.1", I, "Public safety knowledge helps prevent violence and harm."),
    ("element", "2.C.8.b", "16.6", I, "Knowing law and government helps institutions work fairly and openly."),
    ("element", "2.C.9.a", "9.c", D, "Telecommunications knowledge builds the networks people reach ICT through."),
    ("element", "2.C.9.b", "16.10", I, "Media knowledge helps information reach the public."),
    ("element", "2.C.10", "11.2", I, "Transport knowledge is needed for safe, efficient transport systems."),
]
SKILL_REASON = "Basic and cross-functional skills are the relevant skills for employment that target 4.4 counts."


def read(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    occ = [r["occ_id"] for r in read("occupations.csv")]
    elements = read("elements.csv")
    known = {"field": {r["field_id"] for r in read("fields.csv")}, "minor": {o[:4] for o in occ},
             "broad": {o[:7] for o in occ}, "occupation": set(occ), "element": {e["element_id"] for e in elements}}
    rules = list(RULES) + [("element", e["element_id"], "4.4", I, SKILL_REASON)
                           for e in elements if e["kind"] == "skill"]
    rows = []
    for i, (level, code, target, strength, reason) in enumerate(rules, 1):
        if code not in known[level]:
            sys.exit(f"Unknown {level} '{code}' in the SDG rules")
        goal = int(target.split(".")[0])
        rows.append({"sdg_id": f"S{i:03d}", "entity_type": level, "entity_id": code, "sdg_goal": goal,
                     "sdg_goal_name": GOALS[goal], "sdg_target": target, "link_strength": strength,
                     "rationale": reason, **SOURCE})
    with (DATA / "sdg_map.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to data/sdg_map.csv ({len({r['sdg_target'] for r in rows})} targets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

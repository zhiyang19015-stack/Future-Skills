import json, csv, re, sys, os
D = os.path.dirname(os.path.abspath(__file__))
L = {}
def p(k, acc, na, note):
    L[k] = {"acceptable": acc.split(), "not_acceptable": na.split(), "note": note}

p("E01", "29-1141.00 29-2011.00 29-2012.00 29-2034.00 29-1126.00 29-2032.00 29-2061.00 31-1131.00 31-2021.00 31-2011.00 31-1121.00 31-1122.00 31-9092.00 29-2051.00 29-2052.00 29-2043.00",
  "", "SPM science leaver who will study up to a degree and likes caring: nursing, allied health technician and care roles up to job zone 4; no clear mistakes since nothing in her fields exceeds zone 5.")
p("E02", "17-3023.00 17-3024.00 17-3012.00 47-2111.00 49-2094.00 49-2095.00 49-9041.00 49-9071.00 49-9012.00 49-2092.00 17-3024.01 49-9021.00 17-3027.00 49-9043.00 49-2098.00",
  "25-1194.00 11-9041.00 17-2199.06 25-1032.00", "Diploma electrical student, no further study: zone-3 electrical technician and maintenance roles; zone-5 engineering roles and teaching (disliked) are mistakes.")
p("E03", "15-1252.00 15-1251.00 15-1254.00 15-1253.00 15-2051.00 15-2051.01 15-1242.00 15-1243.00 15-1243.01 15-1211.00 15-1212.00 15-1299.07 15-1255.00 15-1255.01 15-1299.08 15-1299.04",
  "25-1021.00 25-1022.00", "CS graduate who codes in Python/JS/SQL: developer, data and security roles at zone 4; postsecondary teaching is people-facing, which he dislikes.")
p("E04", "13-2011.00 13-2031.00 13-2041.00 13-2061.00 13-2081.00 13-2082.00 13-2099.04 13-1041.00 13-1051.00 13-1111.00 13-2053.00 13-2072.00 43-3031.00",
  "13-1011.00", "Accounting graduate who likes rules and numbers: accounting, audit, tax, credit and compliance roles; artist-management work goes against her dislike of the arts.")
p("E05", "27-1024.00 27-1014.00 27-1013.00 27-1012.00 27-1021.00 27-1022.00 27-1025.00 27-1026.00 15-1255.00 43-9031.00 27-4021.00 27-4032.00 15-1255.01",
  "43-9081.00 43-9021.00", "Art-and-design foundation, will study one level: design and visual roles up to zone 4; routine proofreading or data entry goes against his dislike of paperwork.")
p("E06", "25-2021.00 25-2022.00 25-2031.00 25-2012.00 25-2011.00 25-2056.00 25-2057.00 25-2055.00 25-3011.00 25-3041.00 25-3021.00 25-3031.00 25-9042.00 27-3091.00",
  "25-2032.00 25-1194.00 25-2023.00", "TESL graduate who likes teaching children: school, ESL and tutoring roles at zone 4 or below; vocational/technical teaching clashes with her dislike of machines and manual work.")
p("E07", "49-3023.00 49-3052.00 49-3021.00 49-3031.00 49-3053.00 49-3042.00 49-3041.00 49-3093.00 49-3022.00 49-2096.00 17-3027.01 49-3092.00 49-3051.00 53-6031.00 49-3011.00",
  "41-2022.00 41-2021.00 43-5032.00 13-1032.00", "SPM leaver who fixes vehicles and will take a TVET certificate: vehicle mechanic roles up to zone 3; parts/counter sales, dispatch and appraisal are desk or customer work he dislikes.")
p("E08", "19-2041.00 19-2043.00 19-4042.00 19-1031.00 19-1023.00 19-2041.02 11-9121.02 19-3092.00 15-1299.02 19-2099.01 19-4099.03 19-4071.00 19-1031.03 19-4021.00 19-1013.00 19-1029.04 13-1041.01",
  "41-4011.07 41-4011.00", "Environmental science graduate with ArcGIS/R who may do a master's: environmental science, water, conservation and GIS roles up to zone 5; sales roles go against her stated dislike.")
p("E09", "23-1011.00 23-1012.00 23-1022.00 23-2011.00 13-1041.00 11-9199.02 13-1041.07 13-1041.03 13-1075.00",
  "23-1023.00 23-1021.00", "LLB student planning to qualify for practice: lawyer, law clerk, mediation and compliance roles; judgeships need many years of practice and appointment, not a next move.")
p("E10", "35-1011.00 35-2014.00 35-1012.00 11-9051.00 51-3011.00 35-2013.00 35-3023.01 35-2012.00",
  "29-1031.00", "Culinary diploma holder who wants a kitchen and later her own cafe: chef, cook, baker and food service manager roles; dietitian needs zone 5 and registration.")
p("E11", "43-3031.00 43-4161.00 43-3021.00 43-1011.00 43-6011.00 13-2082.00 13-2081.00 43-3061.00 11-3012.00 43-3011.00 43-6014.00 43-4131.00",
  "13-2011.00 13-2099.01 43-9031.00", "Payroll clerk with a diploma, no more study: bookkeeping, HR admin, tax and office supervision at zone 3 or below; accountant needs the degree he refuses, quant is zone 5, desktop publishing is creative work he dislikes.")
p("E12", "29-1141.01 29-1141.03 11-9111.00 11-9121.01 21-1091.00",
  "29-1215.00 29-1151.00 29-1171.00", "Registered nurse who will not study further: specialist acute/critical care nursing, nurse manager, research nurse and health education; physician, nurse anaesthetist and nurse practitioner need licences or degrees beyond her plans.")
p("E13", "43-4171.00 43-6014.00 43-9061.00 43-1011.00 43-3011.00 41-3091.00 43-9041.00 43-4141.00 43-4131.00 43-6013.00 43-4081.00 43-4181.00 43-4061.00 43-4151.00 41-3011.00 41-3041.00",
  "43-9031.00 41-9041.00", "Call-centre agent with SPM who will take a certificate: office, clerical and service-sales roles up to zone 3; telemarketing is as unsteady as his current job and desktop publishing is creative work he dislikes.")
p("E14", "27-1011.00 15-1255.00 27-1021.00 27-1014.00 15-1255.01 27-1025.00 27-1013.00 27-4032.00 11-2011.00 27-1022.00 27-4021.00",
  "43-9031.00 51-5111.00", "Graphic designer wanting to stay creative: art direction, UX/interface, product and motion design at zone 4; desktop publishing and prepress are routine production work leaving the creative side.")
p("E15", "51-9162.00 51-9061.00 51-4081.00 51-4035.00 51-4034.00 51-4033.00 51-4032.00 51-4031.00 49-9044.00 17-3029.01 51-4194.00 51-4122.00",
  "17-2112.03 17-2112.00 11-3051.01 11-3051.00 25-1194.00", "CNC operator with SPM, no further study: CNC programming, machine setting, inspection and millwright roles at zone 2; engineer and production-manager roles need zone 4, and teaching goes against his dislike of helping roles.")
p("E16", "13-1071.00 13-1151.00 13-1141.00 13-1075.00 11-3121.00 11-3131.00 11-3111.00 13-1041.03",
  "", "HR graduate working as an HR assistant: HR specialist, training, compensation and HR manager roles at zone 4; no clear mistakes near her fields.")
p("E17", "13-1151.00 11-3131.00 25-3011.00 25-3041.00 25-3021.00 15-2051.00 15-2051.01 43-9111.00 15-2011.00",
  "25-2032.00 25-1194.00", "Maths teacher with no further study: training, adult education, tutoring and maths/data roles at zone 4; vocational/technical teaching clashes with his dislike of hands-on work.")
p("E18", "43-6012.00 23-2093.00 43-4031.00 43-6011.00 27-3092.00 13-1041.08 13-2081.00",
  "23-1011.00 23-1012.00 23-1022.00 23-1023.00", "Paralegal with a law diploma, no degree planned: legal secretary, title/court clerk and regulatory clerical roles at zone 3; lawyer, law clerk, mediator and judge need a law degree and admission.")
p("E19", "11-9021.00 13-1082.00 17-2051.01 17-2051.02 17-2081.00 13-1051.00 47-4011.00 47-1011.00 17-2111.00 17-1022.00 17-2111.02 17-2151.00",
  "17-1011.00 25-1032.00", "Civil engineer wanting project or construction management: construction/project management, cost estimating and related civil specialties; architect needs a separate registration and teaching goes against his dislike of helping roles.")
p("E20", "11-2021.00 11-2011.00 13-1161.01 27-3031.00 11-2032.00 15-2051.01 11-2022.00 13-1199.06 41-3011.00 13-1121.00",
  "27-1026.00", "Marketing executive aiming for management, analytics or brand: marketing/advertising/PR management, search marketing and BI analysis; window display is hands-on work she dislikes.")
p("E21", "15-1232.00 15-1231.00 15-1254.00 15-1253.00 15-1251.00 15-1252.00 15-1244.00 15-1242.00 15-1299.01 15-1299.08 15-2051.01 15-1211.00 49-2011.00",
  "25-1021.00", "IT diploma holder learning Python who will study one level: IT support, testing, web and junior developer roles up to zone 4; teaching CS is a helping role he dislikes.")
p("E22", "15-2051.00 15-2051.01 15-1242.00 15-1243.01 43-9111.00 13-2041.00 13-2031.00 13-2061.00 13-1111.00 13-1081.02 13-2099.04 13-2011.00 13-1161.00 13-2053.00 13-2072.00 15-1211.00",
  "15-1255.00 15-1255.01", "Finance graduate teller with Power BI/SQL: data, BI and financial analysis roles at zone 4; interface and game design are creative work she dislikes.")
p("E23", "33-9021.00 33-9032.00 33-1091.00 33-9099.02 33-9031.00 33-9093.00 13-1041.04 33-2021.00",
  "13-1041.06", "Retiring police officer with a diploma: private investigation, security supervision and loss prevention at zone 3 or below; coroner needs legal or medical qualification he lacks.")
p("E24", "13-1151.00 13-1071.00 11-3131.00 13-1121.00 25-3011.00 25-3021.00 43-4161.00 25-1194.00 13-1075.00 25-3041.00",
  "53-1044.00", "Flight attendant who trains crew and will study one level: training, HR and adult/vocational teaching up to zone 4; cabin-crew supervision keeps her flying, against her wish for a ground job.")
p("E25", "17-3023.00 17-3024.00 49-2094.00 49-2096.00 47-2111.00 49-2092.00 49-2098.00 49-2022.00 49-2097.00 49-2011.00 17-3024.01 51-9141.00 17-3012.00 49-9062.00 49-2095.00",
  "17-2199.06 17-2199.09 11-9041.00", "Assembly worker with SPM who will take a skills certificate: electrical/electronics technician and repair roles up to zone 3; zone-5 micro/nano engineering and engineering management are out of reach.")
p("E26", "27-3031.00 27-3041.00 27-3042.00 27-3043.00 11-2032.00 27-3011.00 43-9081.00 13-1161.00 13-1161.01 13-1131.00 27-2012.00 11-2011.00 27-3043.05",
  "27-4011.00 27-4031.00 27-4012.00", "Reporter wanting writing/communications work: PR, editing, technical and content writing at zone 4; AV, camera and broadcast technician roles are hands-on work he dislikes.")
p("E27", "21-1021.00 21-1093.00 21-1094.00 21-1091.00 25-9043.00 25-2051.00 39-9041.00 11-9031.00 11-9151.00",
  "19-3033.00 19-3034.00", "Preschool teacher with a diploma who will study one level: child/family social work and human-service roles up to zone 4; psychologist roles need a master's and registration beyond her plans.")
p("E28", "19-4013.00 19-1012.00 19-4099.01 51-9061.00 19-5011.00 19-5012.00 19-4031.00 19-4021.00 45-2011.00 11-3051.01 19-1022.00",
  "35-2014.00 35-1012.00 11-9051.00 35-2013.00", "Head chef leaving long kitchen hours: food science, quality control and food-safety roles up to zone 4; further cook or food-service management roles keep the hours he wants to escape.")
p("E29", "43-5032.00 43-5011.00 43-5011.01 43-5071.00 43-5061.00 53-1042.00 43-5111.00 53-6051.07 43-4151.00 43-9061.00 43-3061.00 43-4181.00",
  "13-1081.00 13-1081.02 11-3071.00 11-3071.04 53-6051.00 53-3033.00 53-3052.00 53-3031.00 53-7062.00", "Lorry driver with SPM who must stop driving: dispatch, freight and logistics clerical roles at zone 2; logistician/manager roles need zone 4, and driving or manual loading is ruled out by his back.")
p("E30", "11-9121.01 13-1041.07 11-9199.01 19-1042.00 19-1021.00 19-2031.00 15-2051.02 19-1041.00 13-1041.00 15-1211.01 11-9121.00",
  "29-2052.00 31-9095.00 29-1216.00", "Pharmacist with a master's leaving retail: clinical research, regulatory affairs and medical science roles up to zone 5; pharmacy technician/aide are more counter work, and physician needs a medical licence.")
p("E31", "19-4031.00 19-2031.00 19-4099.01 19-4013.00 19-4021.00 19-4042.00 19-4092.00 19-2032.00 19-1012.00",
  "41-4011.00 29-1051.00", "Chemistry graduate wanting lab work: chemical, QC, food and forensic lab roles at zone 4 or below; technical sales goes against her dislike of persuading and pharmacist needs a licence she cannot get.")
p("E32", "15-1232.00 15-1244.00 15-1299.08 15-1241.01 49-2011.00 49-2022.00 49-2021.00 49-9052.00 49-2098.00 49-2097.00",
  "15-1221.00 15-2041.00 15-2031.00 15-2021.00 15-1255.00 15-1255.01", "Networking diploma holder: IT support, network administration and telecom installer roles at zone 3; zone-5 research/maths roles are out of reach and design roles clash with his dislike of creative work.")
p("E33", "27-3031.00 27-3043.00 27-3041.00 13-1161.00 13-1161.01 27-3011.00 27-2012.00 27-4032.00 27-4021.00 27-3023.00 41-3011.00 27-4031.00",
  "43-9081.00", "Mass-communication graduate running social media: PR, content, marketing and media production roles; proofreading is routine records work she dislikes.")
p("E34", "43-5061.00 51-9061.00 19-4099.01 17-3026.00 11-3012.00 11-3013.00 53-1043.00 53-1042.00",
  "11-1011.00 11-9041.00", "Retrenched production supervisor with a diploma: production planning, quality, industrial technician and operations supervision at zone 3; chief executive and engineering manager need zone 5.")
p("E35", "41-4012.00 41-4011.00 41-3091.00 41-3021.00 41-3031.00 41-3011.00 13-1161.00 13-1161.01 41-9022.00 13-2072.00 13-1023.00 13-1199.06 41-1012.00 13-1121.00",
  "", "Business graduate who likes clients and targets: B2B and service sales, marketing, purchasing and business development roles at zone 4; no clear mistakes under the rules.")
p("E36", "51-6052.00 51-6051.00 51-6031.00 51-6093.00 39-3092.00 51-6021.00 51-6062.00 51-6041.00 51-6011.00 27-1023.00",
  "27-1025.00 27-1027.00 27-1021.00 27-1024.00", "SPM with a tailoring certificate: tailoring, sewing, upholstery and similar craft work at zone 2; interior, set, industrial and graphic design need zone 4 or 5.")
p("E37", "17-2141.00 17-2112.03 17-2112.00 17-2141.02 17-2199.05 17-2199.08 17-2011.00 17-2131.00 17-2199.03 17-2112.02 17-3013.00 17-3027.00 17-2199.11 17-2141.01 17-2121.00",
  "25-1032.00", "Mechanical engineering graduate with SolidWorks/MATLAB: mechanical, manufacturing and related engineering roles; teaching is a helping role he dislikes.")
p("E38", "43-4081.00 39-7012.00 39-6012.00 35-3031.00 35-9031.00 35-3023.01 35-3011.00 43-4181.00 39-6011.00 39-3091.00 35-3041.00 41-2031.00 41-2021.00 41-3091.00",
  "11-9081.00 13-1121.00 39-9032.00", "SPM with a hospitality certificate, no more study: front desk, travel guide, restaurant and tourist-facing sales roles at zone 2; lodging manager, event planner and recreation worker need zone 4.")
p("E39", "43-3011.00 43-4141.00 43-4131.00 43-3031.00 43-3021.00 43-4011.00 43-4041.00 43-3071.00 43-6014.00 43-6011.00 43-9061.00 43-1011.00 43-9041.00 13-2082.00",
  "13-2099.01 43-9031.00", "Retrenched bank call-centre agent with a business diploma: banking clerical, collections and admin roles at zone 3 or below; quant analyst needs zone 5 and desktop publishing is creative work he dislikes.")
p("E40", "21-1014.00 21-1011.00 21-1013.00 21-1012.00 21-1015.00 21-1021.00 21-1022.00 21-1023.00 21-1093.00 19-4061.00 19-3033.00 19-3022.00 19-3032.00 21-1091.00 21-1092.00 19-3034.00",
  "29-1223.00 29-1141.02", "Psychology graduate willing to do a master's: counselling, social work, psychology and research roles up to zone 5; psychiatrist and psychiatric nurse need medical or nursing licences.")

out = {"annotator": "independent Claude agent; saw only LABELING.md, annotator_view.md and occupation_list.csv",
       "date": "2026-11-17", "labels": L}
json.dump(out, open(os.path.join(D, "labels.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# verify
occ = {r["occ_id"]: int(r["job_zone"]) for r in csv.DictReader(open(os.path.join(D, "occupation_list.csv"), encoding="utf-8"))}
view = open(os.path.join(D, "annotator_view.md"), encoding="utf-8").read()
prob = []
for blk in re.split(r"\n## ", view)[1:]:
    pid = blk[:3]
    lvl = int(re.search(r"Education level: (\d)", blk).group(1))
    ws = int(re.search(r"will study (\d)", blk).group(1))
    cur = re.search(r"Job now: .*?\((\d\d-\d{4}\.\d\d)\)", blk)
    cur = cur.group(1) if cur else None
    if pid not in L: prob.append(f"{pid} missing"); continue
    a, n = L[pid]["acceptable"], L[pid]["not_acceptable"]
    if not 3 <= len(a) <= 20: prob.append(f"{pid} acc count {len(a)}")
    if not 0 <= len(n) <= 15: prob.append(f"{pid} na count {len(n)}")
    if len(set(a)) != len(a) or len(set(n)) != len(n): prob.append(f"{pid} dup")
    if set(a) & set(n): prob.append(f"{pid} overlap {set(a)&set(n)}")
    for i in a + n:
        if i not in occ: prob.append(f"{pid} unknown {i}")
    for i in a:
        if i in occ and occ[i] > lvl + ws: prob.append(f"{pid} zone {i} {occ[i]} > {lvl+ws}")
        if i == cur: prob.append(f"{pid} current job in acceptable")
    print(pid, len(a), len(n))
print("ids:", len(L), "problems:", prob or "none")

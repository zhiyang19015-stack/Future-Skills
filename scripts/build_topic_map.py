"""Write data/skill_topic_map.csv: which Anthropic Economic Index request topic each technology belongs to.

The Economic Index measures how often people hand a request topic ("Data analysis",
"Accounting and bookkeeping") over to Claude entirely. A technology gets that measure through
the topic its everyday use falls under. The crosswalk is ours, written in two layers:

    TOOL_TOPICS      one technology -> topic, with a reason (the tools people name most)
    CATEGORY_TOPICS  an O*NET technology category -> topic, for every other tool in it
    NO_TOPIC         categories and tools no usage topic describes; they count as neutral

Run after scripts/build_onet.py, then scripts/ai_exposure.py. A topic name that is not in the
pinned Economic Index release stops the script, so a renamed topic is never matched silently.

Usage: python scripts/build_topic_map.py
"""

import csv
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = {"source_name": "Our crosswalk to Anthropic Economic Index request topics (level 1)",
          "source_url": "https://huggingface.co/datasets/Anthropic/EconomicIndex",
          "source_date": date.today().isoformat()}

# tech_id -> (topic, reason)
TOOL_TOPICS = {
    "microsoft-excel": ("Data analysis", "Spreadsheet analysis"),
    "google-sheets": ("Data analysis", "Spreadsheet analysis"),
    "microsoft-office-software": ("Workplace writing", "Office documents"),
    "google-workspace-software": ("Workplace writing", "Office documents"),
    "business-software-applications": ("Workplace writing", "Office documents"),
    "microsoft-outlook": ("Workplace writing", "Work email"),
    "email-software": ("Workplace writing", "Work email"),
    "microsoft-powerpoint": ("Slide decks", "Presentation slides"),
    "microsoft-word": ("Formatted writing", "Formatted documents"),
    "google-docs": ("Formatted writing", "Formatted documents"),
    "adobe-acrobat": ("Document transformation", "Converting and editing PDF documents"),
    "microsoft-visio": ("Workflow diagrams", "Process and workflow diagrams"),
    "microsoft-teams": ("Conversation and meeting intelligence", "Meetings and team chat"),
    "zoom": ("Conversation and meeting intelligence", "Online meetings"),
    "cisco-webex": ("Conversation and meeting intelligence", "Online meetings"),
    "google-meet": ("Conversation and meeting intelligence", "Online meetings"),
    "facebook": ("Promotional writing", "Posts that promote a business"),
    "tiktok": ("Photo and video editing", "Short promotional videos"),
    "hubspot-software": ("CRM", "Customer relationship and marketing platform"),
    "marketo-marketing-automation": ("CRM", "Marketing automation tied to customer records"),
    "blackbaud-the-raiser-s-edge": ("CRM", "Donor relationship management"),
    "ahrefs-site-explorer": ("Ad and traffic diagnosis", "Search traffic analysis"),
    "moz-search-engine-optimization-seo-software": ("Ad and traffic diagnosis", "Search traffic analysis"),
    "screaming-frog-seo-spider": ("Ad and traffic diagnosis", "Search traffic analysis"),
    "semrush": ("Ad and traffic diagnosis", "Search traffic analysis"),
    "adobe-analytics": ("Data analysis", "Web and marketing analytics"),
    "adobe-photoshop-lightroom": ("Photo and video editing", "Photo editing"),
    "adobe-audition": ("Making music", "Audio recording and editing"),
    "unix-shell": ("Shell and systems code", "Shell scripting"),
    "atlassian-bitbucket": ("Git workflow", "Hosted Git repositories"),
    "gitlab": ("Git workflow", "Hosted Git repositories"),
    "perforce-software": ("Git workflow", "Version control"),
    "junit": ("Test writing and running", "Unit tests"),
    "hibernate-orm": ("Data storage", "Mapping code to a database"),
    "intuit-turbotax": ("Accounting and bookkeeping", "Tax returns"),
    "tax-software": ("Accounting and bookkeeping", "Tax returns"),
    "thomson-reuters-westlaw": ("Litigation", "Legal research for cases"),
    "disassembler-software": ("Reverse engineering", "Reading compiled code"),
    "chatbot-software": ("Customer support and service", "Automated customer chat"),
    "learning-management-system-lms": ("Instructional design", "Online courses"),
    "articulate-storyline": ("Instructional design", "E-learning authoring"),
    "trimble-sketchup-pro": ("3D modeling and printing", "3D models"),
    "mcneel-rhinoceros-3d": ("3D modeling and printing", "3D models"),
    "shopify-software": ("Business operations", "Running an online shop"),
    "springshare-libguides": ("Reference documentation", "Library research guides"),
    "procore-software": ("Business operations", "Construction project management"),
    "esri-arcgis-survey-123": ("Data analysis", "Field survey data"),
}

# O*NET technology category -> (topic, reason) for the tools not named above
CATEGORY_TOPICS = {
    "Analytical or scientific software": ("Numerical and scientific methods", "Scientific and engineering computation"),
    "Computer aided design CAD software": ("3D modeling and printing", "Design drawings and 3D models"),
    "Computer aided manufacturing CAM software": ("3D modeling and printing", "Models turned into machine paths"),
    "Graphics or photo imaging software": ("Photo and video editing", "Images and graphics"),
    "Video creation and editing software": ("Photo and video editing", "Video editing"),
    "Data base user interface and query software": ("Data storage", "Databases and records systems"),
    "Data base management system software": ("Data storage", "Databases"),
    "Object oriented data base management software": ("Data storage", "Databases"),
    "Data base reporting software": ("Dashboards and charts", "Reports from data"),
    "Business intelligence and data analysis software": ("Dashboards and charts", "Dashboards and reports"),
    "Geographic information system": ("Data analysis", "Map-based data analysis"),
    "Map creation software": ("Data analysis", "Map-based data analysis"),
    "Development environment software": ("Code design", "Writing programs"),
    "Object or component oriented development software": ("Code design", "Writing programs"),
    "Web platform development software": ("Web front-end", "Building websites"),
    "Application server software": ("Server infrastructure", "Running applications on servers"),
    "Cloud-based management software": ("Server infrastructure", "Cloud services"),
    "Configuration management software": ("Config files", "Server configuration"),
    "File versioning software": ("Git workflow", "Version control"),
    "Enterprise application integration software": ("Automated pipelines", "Connecting systems and automating steps"),
    "Project management software": ("Business operations", "Planning and tracking work"),
    "Enterprise resource planning ERP software": ("Business operations", "Running business processes"),
    "Human resources software": ("Business operations", "Staff records and payroll"),
    "Inventory management software": ("Business operations", "Stock and inventory"),
    "Procurement software": ("Business operations", "Purchasing and orders"),
    "Time accounting software": ("Business operations", "Working-time records"),
    "Materials requirements planning logistics and supply chain software": ("Business operations", "Logistics"),
    "Mobile location based services software": ("Business operations", "Transport planning"),
    "Cloud-based data access and sharing software": ("Business operations", "Team coordination"),
    "Accounting software": ("Accounting and bookkeeping", "Accounts and expenses"),
    "Tax preparation software": ("Accounting and bookkeeping", "Tax returns"),
    "Compliance software": ("Business compliance", "Compliance records"),
    "Sales and marketing software": ("Ad campaigns", "Online advertising"),
    "Customer relationship management CRM software": ("CRM", "Customer records"),
    "Computer based training software": ("Instructional design", "Training content"),
    "Word processing software": ("Formatted writing", "Documents"),
    "Office suite software": ("Workplace writing", "Office documents"),
    "Spreadsheet software": ("Data analysis", "Spreadsheet analysis"),
    "Presentation software": ("Slide decks", "Presentation slides"),
    "Document management software": ("Document transformation", "Documents"),
    "Process mapping and design software": ("Workflow diagrams", "Process diagrams"),
    "Program testing software": ("Test writing and running", "Software tests"),
    "Music or sound editing software": ("Making music", "Audio"),
    "Metadata management software": ("Git workflow", "Versioned assets"),
}

# Left neutral on purpose: no request topic describes how these are used
NO_TOPIC = {
    "Medical software": "Clinical record and practice systems: no usage topic describes them",
    "Internet browser software": "A browser is used for everything; no single topic",
    "Point of sale POS software": "Shop tills: no usage topic describes them",
    "Network monitoring software": "Radio network planning: no matching usage topic",
    "Operating system software": "Using a device's operating system is not one usage topic",
    "Industrial control software": "Plant control systems: no matching usage topic",
    "Information retrieval or search software": "No single usage topic",
    "Compiler and decompiler software": "No single usage topic",
    "Web page creation and editing software": "No single usage topic",
}
NO_TOOL = {"g-code": "Machine-tool instructions: no matching usage topic",
           "magellan-firmware": "Device firmware: no matching usage topic",
           "outage-management-system-oms": "Power grid operations: no matching usage topic",
           "google-android": "Using a phone's operating system: no matching usage topic",
           "forsk-atoll": "Radio network planning: no matching usage topic"}


def slug(text: str) -> str:
    """A stable id from a name: "C++" -> "c-plus-plus", "C#" -> "c-sharp", "Microsoft Excel" -> "microsoft-excel"."""
    text = text.lower().replace("++", " plus plus").replace("#", " sharp")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def read(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def known_topics() -> set:
    return {r["node_name"] for r in read("aei/aei_extract.csv")
            if r["category_name"] == "request" and r["hierarchy_level"] == "1"}


def main() -> int:
    # keep the reasons already written for each tool (the file's earlier form keyed tools by name)
    old = {r.get("tech_id") or slug(r["skill_name"]): r for r in read("skill_topic_map.csv")}
    topics = known_topics()
    rows = []
    for t in read("technologies.csv"):
        tid, cat = t["tech_id"], t["category"]
        if tid in TOOL_TOPICS:
            topic, why = TOOL_TOPICS[tid]
        elif tid in NO_TOOL:
            topic, why = "", NO_TOOL[tid]
        elif tid in old and old[tid]["topic"] and old[tid]["rationale"] and tid not in TOOL_TOPICS:
            topic, why = old[tid]["topic"], old[tid]["rationale"]
        elif cat in CATEGORY_TOPICS:
            topic, why = CATEGORY_TOPICS[cat]
        else:
            topic, why = "", NO_TOPIC.get(cat, "No usage topic matches this category")
        if topic and topic not in topics:
            sys.exit(f"'{topic}' (for {t['name']}) is not a level-1 topic in the pinned Economic Index release")
        rows.append({"tech_id": tid, "tech_name": t["name"], "tech_category": cat, "topic": topic,
                     "rationale": why, **SOURCE})
    with (DATA / "skill_topic_map.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to data/skill_topic_map.csv; {sum(1 for r in rows if r['topic'])} with a topic")
    return 0


if __name__ == "__main__":
    sys.exit(main())

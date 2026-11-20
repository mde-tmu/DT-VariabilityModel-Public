"""FeatureIDE colour scheme for the DT feature model (one colour per subsystem).

FeatureIDE 3.11 stores feature colours in <project>/.profiles/<scheme>.profile and
reads them once per Eclipse session (restart Eclipse after adding the file to a
project that is already open)."""
import os
import xml.etree.ElementTree as ET

GROUPS = ("and", "or", "alt", "feature")
SUBSYSTEM_COLOR = {  # names are FeatureIDE's FeatureColor values
    "Twinning_System": "Pink", "Cyber_Physical_System": "Cyan",
    "Architecture_System": "Yellow", "Deployment_Runtime": "Blue",
    "User_Interface": "Dark_Green", "Connectivity_System": "Orange",
    "Data_Integration_System": "Light_Green", "Goal_and_Capability_System": "Magenta",
    "Security_System": "Red", "Standards_Compliance": "Light_Gray",
}


def write_profile(model_path, project_dir, scheme="ee"):
    root = ET.parse(model_path).getroot().find("struct")[0]
    lines = ["true"]
    for top in root:
        color = SUBSYSTEM_COLOR.get(top.get("name"))
        if top.tag in GROUPS and color:
            lines += [f"{e.get('name')}={color}" for e in top.iter() if e.tag in GROUPS]
    d = os.path.join(project_dir, ".profiles")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, scheme + ".profile"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

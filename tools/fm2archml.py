#!/usr/bin/env python3
"""Transform a FeatureIDE configuration of the DT feature model into an
ArchML4IoT architecture model (.archml4iot, XMI).

Only the physical / architectural slice of the feature model has an
ArchML4IoT counterpart (CPS, User_Interface, Connectivity_System).  Twinning,
reasoning, goals, security etc. are out of scope and reported as such.

Usage:
    fm2archml.py CONFIG.xml [-o OUT.archml4iot] [--name "Smart Home"]

CONFIG.xml is a FeatureIDE configuration (<configuration><feature .../>).
A feature counts as selected when manual="selected" or automatic="selected".
"""
import argparse
from fide_colors import write_profile
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

NS = "http://www.example.org/archML4IoT"
XMI = "http://www.omg.org/XMI"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("archML4IoT", NS)
ET.register_namespace("xmi", XMI)
ET.register_namespace("xsi", XSI)

# feature name -> ArchML4IoT enum literal.  None = no literal in the metamodel
# (the device is still created, with a name but no `type`, and a warning).
SENSOR = {
    "Flame": "Infrared_Flame_Sensor", "Ultrasonic": "Ultrasonic_Sensor",
    "PIR": "Infrared_Sensor", "Temperature": "Thermometer",
    "Heat": "Thermometer", "Pressure": "Pressure_Sensor",
    "Vibration": None, "LDR": None, "Proximity": None, "Other": None,
}
ACTUATOR = {
    "LED": "LED_Kit", "Alarm": "Speaker", "Buzzer": "Buzzer",
    "Servo": "Motor", "Motor": "Motor", "Pneumatic": "Solenoid",
}
CONTROLLER = {
    "Single_board_Controllers": "Microcontroller_Units",
    "Single_board_Computer": "Single_Board_Computers",
    "Industrial_PLCs": "Programmable_Logic_Controllers",
    "Micro_Processors": None, "Emulator": None,
}
# Literals of the ArchML4IoT enums, used to type features that have no table entry.
SENSOR_LITS = ["Infrared_Flame_Sensor", "Gas_Sensor", "Ultrasonic_Sensor", "Thermometer",
               "Humidity_Sensor", "Barometric_Pressure_Sensor", "Gyroscope", "Pressure_Sensor",
               "Infrared_Sensor", "Power_Sensor", "Heart_Rate_Sensor", "Body_Temperature_Sensor"]
ACTUATOR_LITS = ["Water_Pump", "Buzzer", "LED_Kit", "Motor", "Speaker", "Heater", "Solenoid"]
# v2 model (EDT-VariabilityModel-Public) feature names; the v1 names above stay supported.
SENSOR.update({
    "Flame_Sensor": "Infrared_Flame_Sensor", "Heat_Sensor": "Thermometer",
    "Ultrasonic_Sensor": "Ultrasonic_Sensor", "PIR_Sensor": "Infrared_Sensor",
    "Temperature_Sensor": "Thermometer", "Humidity_Sensor": "Humidity_Sensor",
    "Gas_Sensor": "Gas_Sensor", "Pressure_Sensor": "Pressure_Sensor",
    "IMU_Sensor": "Gyroscope", "LDR_Sensor": None, "Vibration_Sensor": None,
    "Proximity_Sensor": None, "LiDAR": None, "Radar": None, "RFID": None,
    "Camera_Sensor": None,
})
ACTUATOR.update({
    "Servo_Motor": "Motor", "DC_Motor": "Motor", "AC_Motor": "Motor",
    "Stepper_Motor": "Motor", "Linear_Motor": "Motor",
    "Pneumatic_Actuator": "Solenoid", "Hydraulic_Actuator": "Solenoid",
    "Solenoid_Valve": "Solenoid", "Relay": None, "Piezoelectric_Actuator": None,
})
CONTROLLER.update({
    "Single_Board_Controller": "Microcontroller_Units",
    "Single_Board_Computer": "Single_Board_Computers",
    "Industrial_PLC": "Programmable_Logic_Controllers",
    "FPGA": "FPGA_based_Controllers", "Micro_Processor": None, "DSP": None,
    "GPU": None, "Edge_AI_Accelerator": None,
})
CONTROLLER_LITS = ["Microcontroller_Units", "Single_Board_Computers", "System_on_Module",
                   "Programmable_Logic_Controllers", "FPGA_based_Controllers"]


def guess_literal(feature, table, literals):
    """Table entry first; otherwise a literal equal to the feature name or the
    feature name plus a suffix (Humidity -> Humidity_Sensor, Heater -> Heater)."""
    if feature in table:
        return table[feature]
    norm = lambda x: x.lower().replace("_", "")
    for lit in literals:
        if norm(lit) in (norm(feature), norm(feature) + "sensor", norm(feature) + "kit"):
            return lit
    return None


TAG = {"RFID": ("RFID Tag", "RFID")}  # feature -> (device name, TagType literal)
CLOUD = {"GCP": "GCP", "AWS": "AWS", "Azure": "Azure", "Custom": "Custom Cloud",
         "Custom_Cloud": "Custom Cloud"}
# Features of the model that carry no architecture information in ArchML4IoT.
OUT_OF_SCOPE_ROOTS = ("Twinning_System", "Goal_and_Capability_System",
                      "Security_System", "Standards_Compliance")


def selected_features(path):
    sel = set()
    for f in ET.parse(path).getroot().iter("feature"):
        if "selected" in (f.get("manual"), f.get("automatic")) \
                and f.get("manual") != "unselected" \
                and f.get("automatic") != "unselected":
            name = f.get("name")
            if any(ch.isalnum() for ch in name):  # skip "......" placeholders
                sel.add(name)
    return sel


def descendants(model_path, group):
    """Names of all features below the (first) feature called `group`."""
    out = set()
    for el in ET.parse(model_path).getroot().iter():
        if el.get("name") == group:
            for d in el.iter():
                n = d.get("name")
                if d is not el and n and any(ch.isalnum() for ch in n) \
                        and d.tag in ("feature", "and", "or", "alt"):
                    out.add(n)
            break
    return out


def build(sel, system_name, warn, groups, logic="Logic_Unit"):
    q = lambda t: f"{{{NS}}}{t}"
    xsi_type = f"{{{XSI}}}type"
    lists = {k: [] for k in (
        "system", "physical_entity", "virtual_entity", "resource", "system_hub",
        "controller", "user_interface", "network_device", "device",
        "arch_frame")}

    def add(kind, **attrs):
        lists[kind].append(attrs)
        return f"//@{kind}.{len(lists[kind]) - 1}"

    # --- devices -----------------------------------------------------------
    sensors, actuators, tags = [], [], []
    for feat in sorted(sel & groups["sensors"], key=lambda f: list(SENSOR).index(f) if f in SENSOR else 999):
        if feat in TAG:  # RFID readers are Tags in ArchML4IoT, not Sensors
            tags.append(add("device", xsi="Tag", name=TAG[feat][0], type=TAG[feat][1]))
            continue
        lit = guess_literal(feat, SENSOR, SENSOR_LITS)
        if lit is None:
            warn(f"sensor '{feat}' has no SensorType literal; created untyped")
        a = {"xsi": "Sensor", "name": feat}
        if lit:
            a["type"] = lit
        sensors.append(add("device", **a))
    for feat in sorted(sel & groups["actuators"], key=lambda f: list(ACTUATOR).index(f) if f in ACTUATOR else 999):
        lit = guess_literal(feat, ACTUATOR, ACTUATOR_LITS)
        if lit is None:
            warn(f"actuator '{feat}' has no ActuatorType literal; created untyped")
        a = {"xsi": "Actuator", "name": feat}
        if lit:
            a["type"] = lit
        actuators.append(add("device", **a))
    devices = actuators + sensors + tags

    # --- resources ---------------------------------------------------------
    # Controller.store has lowerBound=1, so an on-device resource always exists.
    local = add("resource", xsi="On_Device_Resource", name="Local Resource")
    cloud_names = [CLOUD.get(f, f) for f in sorted(sel & groups["clouds"])]
    wants_cloud = bool(cloud_names) or "Cloud_Integration" in sel \
        or "Online" in sel or "Cloud_Layer" in sel
    clouds = []
    if wants_cloud:
        for n in cloud_names or ["Cloud Database"]:
            idx = len(lists["resource"])
            ref = f"//@resource.{idx}"
            clouds.append(add(
                "resource", xsi="Environment_Data", name=n, computing="Cloud",
                environment_data=ref, sensor=" ".join(sensors), tag=" ".join(tags),
                env_name="Virtual Env"))
    else:
        warn("no cloud integration selected; no Cloud resource created")

    # --- controller --------------------------------------------------------
    ctype = [(f, guess_literal(f, CONTROLLER, CONTROLLER_LITS)) for f in sorted(sel & groups["controllers"])]
    if not ctype:
        warn("no Computation_Model selected; controller created untyped")
    if ctype and ctype[0][1] is None:
        warn(f"controller '{ctype[0][0]}' has no ControllerType literal; created untyped")
    if len(ctype) > 1:
        warn("several computation models selected; using the first for the controller type")
    net = None
    if wants_cloud:
        net = add("network_device", name="WiFi Adapter",
                  cloud_database=" ".join(clouds))
        warn("network technology is not in the feature model; assumed WiFi adapter")
    # `core` (LogicType) otherwise defaults to the first literal, Garage_Door.
    c = {"xsi": "Logic_Unit", "name": "Controller", "core": logic,
         "store": local, "device": " ".join(devices)}
    c["logic_unit"] = "//@controller.0"  # Logic_Unit refers to itself in the samples
    if net:
        c["network_device"] = net
    if ctype and ctype[0][1]:
        c["type"] = ctype[0][1]
    ctrl = add("controller", **c)

    # --- physical entity ---------------------------------------------------
    pe = add("physical_entity", controller=ctrl, name="Physical Entity")

    # --- user interfaces / hub --------------------------------------------
    uis = []
    if "Dashboard" in sel:
        uis.append(add("user_interface", xsi="Dashboard", name="Dashboard"))
    if "App" in sel:
        uis.append(add("user_interface", xsi="Mobile_App", name="App"))
    hub = None
    if uis or clouds:
        hub = add("system_hub", user_interface=" ".join(uis), name="Server",
                  access=" ".join([local] + clouds))

    # --- virtual entity ----------------------------------------------------
    ve = None
    if hub or clouds:
        ve = add("virtual_entity", resource=" ".join([local] + clouds),
                 system_hub=hub or "", name="Virtual Entity")

    # --- system + frames ---------------------------------------------------
    sysattrs = {"physical_entity": pe, "name": system_name}
    if ve:
        sysattrs["virtual_entity"] = ve
    add("system", **sysattrs)
    add("arch_frame", name="Edge Layer and Devices")
    if clouds:
        add("arch_frame", name="Cloud Layer")

    return lists


def to_xml(lists, system_name):
    root = ET.Element(f"{{{NS}}}ArchML4IoT")
    root.set(f"{{{XMI}}}version", "2.0")
    order = ["system", "physical_entity", "virtual_entity", "resource",
             "system_hub", "controller", "user_interface", "network_device",
             "device", "arch_frame"]
    for kind in order:
        for attrs in lists[kind]:
            e = ET.SubElement(root, kind)
            a = dict(attrs)
            t = a.pop("xsi", None)
            if t:
                e.set(f"{{{XSI}}}type", f"archML4IoT:{t}")
            for k, v in a.items():
                if v not in (None, ""):
                    e.set(k, v)
    ET.indent(root)
    return ET.ElementTree(root)


PROJECT_FILE = """<?xml version="1.0" encoding="UTF-8"?>
<projectDescription>
\t<name>{name}</name>
\t<comment></comment>
\t<projects>
\t</projects>
\t<buildSpec>
\t</buildSpec>
\t<natures>
\t\t<nature>org.eclipse.sirius.nature.modelingproject</nature>
\t</natures>
</projectDescription>
"""

# Sirius session file: semantic model + the ArchML4IoT viewpoint (registered by the
# tmu.ArchML4IoT.design plugin). Representations are created inside Eclipse.
AIRD = """<?xml version="1.0" encoding="UTF-8"?>
<viewpoint:DAnalysis xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:viewpoint="http://www.eclipse.org/sirius/1.1.0">
  <semanticResources>{model}</semanticResources>
  <ownedViews xmi:type="viewpoint:DView" viewpoint="viewpoint:/tmu.ArchML4IoT.design/ArchML4IoT"/>
</viewpoint:DAnalysis>
"""

README = """# {name}

ArchML4IoT project generated from a feature-model configuration by fm2archml.py.

- `{base}.archml4iot`  the architecture model
- `{base}.aird`        Sirius session (ArchML4IoT viewpoint already selected)
- `feature-model/`     the configuration (and model.xml) it was generated from

## Open in Eclipse (runtime workbench with ArchML4IoT installed)
1. File > Import > General > Existing Projects into Workspace > select this folder.
2. Open `{base}.aird`; expand it in Model Explorer.
3. Right-click the root `ArchML4IoT` element > New Representation > ArchML4IoT.
   If the diagram is empty, drag the elements in from Model Explorer.
"""


def write_project(outdir, name, tree, config, model):
    base = re.sub(r"[^A-Za-z0-9_-]+", "", name.replace(" ", "")) or "System"
    os.makedirs(os.path.join(outdir, "feature-model"), exist_ok=True)
    tree.write(os.path.join(outdir, base + ".archml4iot"), encoding="UTF-8", xml_declaration=True)
    for fn, txt in ((".project", PROJECT_FILE.format(name=base)),
                    (base + ".aird", AIRD.format(model=base + ".archml4iot")),
                    ("README.md", README.format(name=name, base=base))):
        with open(os.path.join(outdir, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
    shutil.copy(config, os.path.join(outdir, "feature-model", os.path.basename(config)))
    if model:
        shutil.copy(model, os.path.join(outdir, "feature-model", "model.xml"))
    return base


# Subtrees of the feature model that ArchML4IoT can express.  Everything else
# (Twinning_System, Security_System, ...) is left as a feature model.
TRANSFORMED = ("Cyber_Physical_System", "User_Interface", "Connectivity_System")
FEATURE_GROUPS = ("and", "or", "alt", "feature")


def write_residual(outdir, model, config):
    """Feature model + configuration with the transformed subtrees removed and
    everything else untouched."""
    mt = ET.parse(model)
    struct = mt.getroot().find("struct")
    root = struct[0]
    removed = set()
    for parent in list(root.iter()):
        for child in list(parent):
            if child.get("name") in TRANSFORMED:
                removed.update(e.get("name") for e in child.iter() if e.get("name"))
                parent.remove(child)
    kept = {e.get("name") for e in root.iter() if e.tag in FEATURE_GROUPS and e.get("name")}
    cons = mt.getroot().find("constraints")
    dropped = 0
    if cons is not None:
        for rule in list(cons):
            if not {v.text for v in rule.iter("var")} <= kept:
                cons.remove(rule)
                dropped += 1
    os.makedirs(os.path.join(outdir, "configs"), exist_ok=True)
    ET.indent(mt)
    mt.write(os.path.join(outdir, "model.xml"), encoding="UTF-8", xml_declaration=True)
    ct = ET.parse(config)
    for f in list(ct.getroot()):
        if f.get("name") in removed or f.get("name") not in kept:
            ct.getroot().remove(f)
    ET.indent(ct)
    ct.write(os.path.join(outdir, "configs", os.path.basename(config)),
             encoding="UTF-8", xml_declaration=True)
    with open(os.path.join(outdir, ".project"), "w", encoding="utf-8", newline="\n") as f:
        f.write(FEATUREIDE_PROJECT.format(name=os.path.basename(os.path.abspath(outdir))))
    write_profile(os.path.join(outdir, "model.xml"), outdir)
    return len(kept), len(removed), dropped


FEATUREIDE_PROJECT = """<?xml version="1.0" encoding="UTF-8"?>
<projectDescription>
\t<name>{name}</name>
\t<comment></comment>
\t<projects>
\t</projects>
\t<buildSpec>
\t\t<buildCommand>
\t\t\t<name>de.ovgu.featureide.core.mpl.MSPLBuilder</name>
\t\t\t<arguments>
\t\t\t\t<dictionary><key>build</key><value>src</value></dictionary>
\t\t\t\t<dictionary><key>composer</key><value>de.ovgu.featureide.core.FeatureModeling</value></dictionary>
\t\t\t\t<dictionary><key>equations</key><value>configs</value></dictionary>
\t\t\t\t<dictionary><key>source</key><value>features</value></dictionary>
\t\t\t</arguments>
\t\t</buildCommand>
\t</buildSpec>
\t<natures>
\t\t<nature>de.ovgu.featureide.core.featureProjectNature</nature>
\t\t<nature>de.ovgu.featureide.core.mpl.MSPLNature</nature>
\t</natures>
</projectDescription>
"""


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("config", help="FeatureIDE configuration XML")
    p.add_argument("-o", "--output", help="output .archml4iot (default: stdout)")
    p.add_argument("-m", "--model", help="FeatureIDE model.xml (default: ../model.xml "
                   "relative to the configs folder, if present). Lets new features under "
                   "Sensors/Actuator/Cloud_Integration/Computation_Model be picked up.")
    p.add_argument("--project", metavar="DIR", help="write a complete Eclipse "
                   "ArchML4IoT project folder (model, .aird, .project) to DIR")
    p.add_argument("--logic", default="Logic_Unit",
                   choices=["Garage_Door", "Smart_Light", "Fire_Alarm", "TV", "Microwave", "Logic_Unit"],
                   help="LogicType of the controller's logic unit (default: Logic_Unit)")
    p.add_argument("--residual", metavar="DIR", help="also write the part that is NOT "
                   "transformed (feature model + configuration, with the CPS / "
                   "User_Interface / Connectivity subtrees removed) as a FeatureIDE project in DIR")
    p.add_argument("--name", default="System", help="ArchML4IoT system name")
    args = p.parse_args()

    warnings = []
    sel = selected_features(args.config)
    model = args.model
    if not model:
        guess = os.path.join(os.path.dirname(os.path.abspath(args.config)), "..", "model.xml")
        model = guess if os.path.exists(guess) else None
    if model:
        groups = {"sensors": descendants(model, "Sensors"),
                  "actuators": descendants(model, "Actuator"),
                  "clouds": descendants(model, "Cloud_Integration"),
                  "controllers": descendants(model, "Computation_Model")}
    else:
        warnings.append("no model.xml found; only the built-in feature names are recognised")
        groups = {"sensors": set(SENSOR), "actuators": set(ACTUATOR),
                  "clouds": set(CLOUD), "controllers": set(CONTROLLER)}
    lists = build(sel, args.name, warnings.append, groups, args.logic)
    tree = to_xml(lists, args.name)
    if args.project:
        base = write_project(args.project, args.name, tree, args.config, model)
        print(f"project written to {args.project} ({base}.archml4iot, {base}.aird)", file=sys.stderr)
    elif args.output:
        tree.write(args.output, encoding="UTF-8", xml_declaration=True)
    else:
        tree.write(sys.stdout.buffer, encoding="UTF-8", xml_declaration=True)
        sys.stdout.buffer.write(b"\n")
    if args.residual:
        if not model:
            sys.exit("--residual needs the model.xml (pass -m)")
        kept, removed, dropped = write_residual(args.residual, model, args.config)
        print(f"residual feature model written to {args.residual}: {kept} features stay, "
              f"{removed} became ArchML4IoT, {dropped} constraint(s) dropped", file=sys.stderr)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    dropped = sorted(s for s in sel if s in OUT_OF_SCOPE_ROOTS)
    if dropped:
        print("note: not representable in ArchML4IoT, skipped: "
              + ", ".join(dropped), file=sys.stderr)


if __name__ == "__main__":
    main()

# ArchML4IoT models generated from the feature model

`tools/fm2archml.py` maps a FeatureIDE configuration of the DT feature model to an
ArchML4IoT architecture model. Only the three subtrees that
describe the cyber-physical architecture are transformed: `Cyber_Physical_System`,
`User_Interface` and `Connectivity_System`. The other subtrees have no ArchML4IoT
counterpart and are reported as skipped.

| System | Configuration | Generated project |
|---|---|---|
| Garage door | [`garage_door.xml`](../DT-Builder-VariabilityModel/FeatureModelDT_v2/configs/garage_door.xml) | [`GarageDoor_ArchML`](GarageDoor_ArchML) |
| Fire alarm | [`fire_alarm.xml`](../DT-Builder-VariabilityModel/FeatureModelDT_v2/configs/fire_alarm.xml) | [`FireAlarm_ArchML`](FireAlarm_ArchML) |
| Smart light | [`smart_light.xml`](../DT-Builder-VariabilityModel/FeatureModelDT_v2/configs/smart_light.xml) | [`SmartLight_ArchML`](SmartLight_ArchML) |
| Smart warehouse | [`smart_warehouse.xml`](../DT-Builder-VariabilityModel/FeatureModelDT_v2/configs/smart_warehouse.xml) | [`Warehouse_ArchML`](Warehouse_ArchML) |

## Regenerating

```sh
M=DT-Builder-VariabilityModel/FeatureModelDT_v2
python3 tools/fm2archml.py $M/configs/garage_door.xml -m $M/model.xml \
  --name "Garage Door" --logic Garage_Door --project archml4iot/GarageDoor_ArchML
```

`--project` writes an Eclipse project (model, `.aird`, `.project`). `--residual DIR`
also writes the part of the feature model that is not transformed.

## What the script assumes

- The configuration is valid for the feature model. The script does not evaluate
  constraints. A feature is used if it is selected and not explicitly unselected.
- Where the ArchML4IoT metamodel has no literal for a feature (a proximity sensor or a
  relay), the element is created without a type and a warning is printed.
- The network technology is not part of the feature model, so a WiFi adapter is
  assumed whenever a cloud resource exists, and a warning is printed.
- Elements the metamodel requires but the feature model does not express are added
  with fixed defaults: an on-device resource, the physical entity, the virtual entity
  (when there is a hub or cloud resource) and the *Edge Layer and Devices* frame (and
  the *Cloud Layer* frame when a cloud resource exists).

Open a generated project in an Eclipse runtime workbench that has ArchML4IoT installed
(File > Import > Existing Projects into Workspace), then open the `.aird` file.

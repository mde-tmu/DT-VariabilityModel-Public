# Complete FeatureIDE configurations

These configurations target `FeatureModelDT_v2/model.xml`.

- `smart_warehouse.xml`: 90 selected features. Supervised software command
  coupling to an edge controller (`Digital_Twin`, `Command_Control`,
  `Human_Supervised`), a single-board edge computer, MQTT as the only
  communication protocol, local networking plus cloud history, streaming/API
  integration, and dashboard/web-app choices.
- `smart_home.xml`: 76 selected features. A statechart model with code
  generation, a single-board controller with home sensors and actuators, app and
  dashboard interfaces, cloud connectivity, and human-actuated or
  human-supervised commands.

- `garage_door.xml`: 47 selected features. A statechart model with code
  generation, a single-board controller with ultrasonic and PIR sensors, an RFID
  reader and a servo motor, an interactive dashboard and an Android app, GCP
  cloud integration, and streaming integration.
- `fire_alarm.xml`: 47 selected features. The same structure as the garage door
  with gas, flame and temperature sensors and a buzzer.
- `smart_light.xml`: 45 selected features. The same structure with a PIR sensor
  and an LED.

The garage door, fire alarm and smart light selections follow the system
descriptions of the ArchML4IoT evaluation (Zha et al.) and are the inputs of
`tools/fm2archml.py`, which generates the ArchML4IoT models in `archml4iot/`.

Both are constructed engineering examples, not implemented systems or evidence of
usefulness/safety.

All 339 feature states are explicit manual selected/unselected values. FeatureIDE
3.12.0 XMLConfFormat writes and re-imports the files, and ConfigurationAnalyzer
checks completeness and validity. Entries that the requirements leave open use
deterministic deselection-preferred completion, not ranking.

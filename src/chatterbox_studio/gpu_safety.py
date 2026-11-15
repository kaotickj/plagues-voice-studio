"""Optional read-only AMD telemetry. No app temperature ceilings or GPU control."""
from pathlib import Path


def read_temperatures(device_root):
    """Return available sensor readings; unavailable telemetry never blocks work."""
    temperatures = {}
    for file in (Path(device_root) / 'hwmon').glob('hwmon*/temp*_input'):
        try:
            label = file.with_name(file.name.replace('_input', '_label')).read_text().strip()
            temperatures[label] = int(file.read_text()) / 1000
        except (OSError, ValueError):
            continue
    return temperatures

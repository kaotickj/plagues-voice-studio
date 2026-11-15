from chatterbox_studio.gpu_safety import read_temperatures


def sensors(tmp_path, **values):
    p = tmp_path / 'hwmon/hwmon0'
    p.mkdir(parents=True, exist_ok=True)
    for n, (label, value) in enumerate(dict(edge=45, junction=50, mem=45).items(), 1):
        (p / f'temp{n}_label').write_text(label)
        (p / f'temp{n}_input').write_text(str(int(values.get(label, value) * 1000)))
    return tmp_path


def test_temperature_reading_has_no_start_or_running_ceilings(tmp_path):
    assert read_temperatures(sensors(tmp_path, junction=99))['junction'] == 99


def test_missing_telemetry_is_optional(tmp_path):
    assert read_temperatures(tmp_path) == {}


def test_bad_sensor_does_not_invent_a_reading_or_block_other_sensors(tmp_path):
    root = sensors(tmp_path)
    (root / 'hwmon/hwmon0/temp2_input').write_text('unavailable')
    assert read_temperatures(root) == {'edge': 45, 'mem': 45}

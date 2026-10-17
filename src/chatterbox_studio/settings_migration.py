"""Non-destructive migration from the former version-specific QSettings identity."""


def copy_legacy_settings(current, legacy) -> int:
    """Copy only missing settings; never overwrite newer user choices.

    Accepts QSettings instances (or duck-typed stand-ins for offline tests).
    Legacy registry/settings data is not removed and can still be used by
    previous releases. A repeat call is harmless.
    """
    if current is legacy:
        return 0
    present = set(current.allKeys())
    count = 0
    for key in legacy.allKeys():
        if key.startswith("migration/") or key in present:
            continue
        current.setValue(key, legacy.value(key))
        count += 1
    if count:
        current.sync()
    return count

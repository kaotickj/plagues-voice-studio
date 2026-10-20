def create_plugin(context):
    from .panel import ScriptPrep
    return ScriptPrep(context)

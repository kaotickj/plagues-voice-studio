"""Generic copywriting plugin entry point. No standalone branding or DJ profiles."""
def create_plugin(context):
    from .panel import PromotionalWriter
    return PromotionalWriter(context)

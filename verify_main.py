
try:
    from agent_pump.cli import main
    print(f"Successfully imported main: {type(main)}")
except Exception as e:
    print(f"Failed to import main: {e}")
except NameError as e:
    print(f"NameError importing main: {e}")

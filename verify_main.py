
try:
    from agent_pump.cli import main
    print(f"Successfully imported main: {type(main)}")
except NameError as e:
    print(f"NameError importing main: {e}")
except Exception as e:
    print(f"Failed to import main: {e}")

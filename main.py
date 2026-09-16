import os
import sys

# Entry point forwarding to Streamlit app in src/triporchestrator/app.py
app_path = os.path.join(os.path.dirname(__file__), "src", "triporchestrator", "app.py")

if __name__ == "__main__":
    if "streamlit" in sys.modules or any("streamlit" in arg for arg in sys.argv):
        # Running via streamlit run main.py
        with open(app_path, "r", encoding="utf-8") as f:
            code = f.read()
        exec(code, globals())
    else:
        # Running via python main.py -> launch streamlit
        import subprocess
        print(f"Launching Streamlit application from {app_path}...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])

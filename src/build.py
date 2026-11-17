"""Build everything: KPI tables, static dashboards, interactive dashboards.

Usage (from the repository root):
    python src/generate_data.py   # optional: regenerate the synthetic data
    python src/build.py
"""
import kpis
import static_dashboards

if __name__ == "__main__":
    k = kpis.load()
    static_dashboards.build_all(k)
    try:
        import interactive_dashboards
        interactive_dashboards.build_all(k)
    except ImportError:
        pass
    print("Built dashboards and KPI tables.")

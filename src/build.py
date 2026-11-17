"""Build everything: KPI tables, static dashboards, interactive dashboards.

Builds KPI tables, static and interactive dashboards, the 8-level analysis, and REPORT.md.

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
    import advanced_analysis
    import write_report
    advanced_analysis.main()
    write_report.main()
    print("Built dashboards, KPI tables, and analysis report.")

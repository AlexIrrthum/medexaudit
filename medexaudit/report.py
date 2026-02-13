"""Phase 5: HTML report generation from audit files."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader

from .models import AuditReport
from .paths import OUTPUT_DIR, TEMPLATES_DIR


def _load_audits(audit_paths: list[str]) -> list[AuditReport]:
    """Load and validate audit JSON files."""
    reports = []
    for p in audit_paths:
        reports.append(AuditReport.model_validate_json(Path(p).read_text(encoding="utf-8")))
    return reports


def _accuracy_bar_chart(reports: list[AuditReport]) -> str:
    """Bar chart: global accuracy score per candidate model."""
    models = [r.candidate_model for r in reports]
    scores = [r.final_metrics.global_accuracy_score for r in reports]

    fig = go.Figure(
        data=[go.Bar(x=models, y=scores, marker_color="#4C78A8")],
        layout=go.Layout(
            title="Global Accuracy Score by Model",
            yaxis_title="Accuracy Score",
            xaxis_title="Candidate Model",
            yaxis_range=[0, 100],
            template="plotly_white",
        ),
    )
    return fig.to_html(include_plotlyjs=True, full_html=False)


def _error_breakdown_chart(reports: list[AuditReport]) -> str:
    """Grouped bar chart: error breakdown by severity per model."""
    models = [r.candidate_model for r in reports]
    critical = []
    major = []
    minor = []

    for r in reports:
        c, m, mi = 0, 0, 0
        for fact_result in r.audit_results:
            for d in fact_result.deductions:
                pts = abs(d.points)
                if pts >= 20:
                    c += 1
                elif pts >= 10:
                    m += 1
                else:
                    mi += 1
        critical.append(c)
        major.append(m)
        minor.append(mi)

    fig = go.Figure(
        data=[
            go.Bar(name="Critical (-20)", x=models, y=critical, marker_color="#E45756"),
            go.Bar(name="Major (-10)", x=models, y=major, marker_color="#F58518"),
            go.Bar(name="Minor (-5)", x=models, y=minor, marker_color="#72B7B2"),
        ],
        layout=go.Layout(
            title="Error Breakdown by Severity",
            barmode="group",
            yaxis_title="Count",
            xaxis_title="Candidate Model",
            template="plotly_white",
        ),
    )
    return fig.to_html(include_plotlyjs=False, full_html=False)


def report(
    audit_paths: list[str],
    output_path: str | None = None,
) -> str:
    """Generate a self-contained HTML report from one or more audit files.

    Loads audit JSONs, builds Plotly charts (accuracy bar chart and error
    breakdown), renders them into a Jinja2 HTML template, and writes a
    single self-contained HTML file.

    Args:
        audit_paths: One or more paths to audit JSON files produced by
            :func:`audit`.
        output_path: Where to write the HTML report. When *None* a
            timestamped path under ``output/`` is generated.

    Returns:
        The path to the generated HTML report as a string.

    Raises:
        FileNotFoundError: If any path in *audit_paths* does not exist.
        pydantic.ValidationError: If an audit file doesn't match the
            :class:`AuditReport` schema.
    """
    reports = _load_audits(audit_paths)

    accuracy_chart = _accuracy_bar_chart(reports)
    error_chart = _error_breakdown_chart(reports)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("report.html.j2")

    now = datetime.now(timezone.utc)
    html = template.render(
        reports=reports,
        accuracy_chart=accuracy_chart,
        error_chart=error_chart,
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    if output_path is None:
        ts = now.strftime("%Y%m%d_%H%M%S")
        out = OUTPUT_DIR / f"report_{ts}.html"
    else:
        out = Path(output_path)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out)

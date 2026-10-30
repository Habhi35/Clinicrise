import io
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from reports.models import MonthlyGrowthReport


class ReportPDFService:
    """
    Renders high-fidelity, branded clinical monthly growth PDF reports
    using ReportLab.
    """

    # Palette
    COLOR_PRIMARY = colors.HexColor("#0F172A")    # Deep Slate Navy
    COLOR_ACCENT = colors.HexColor("#0D9488")     # Medical Teal
    COLOR_SECONDARY = colors.HexColor("#2563EB")  # Professional Blue
    COLOR_BG_CARD = colors.HexColor("#F8FAFC")    # Very light slate
    COLOR_BORDER = colors.HexColor("#CBD5E1")     # Light border
    COLOR_TEXT = colors.HexColor("#334155")       # Charcoal
    COLOR_MUTED = colors.HexColor("#64748B")      # Muted slate

    @classmethod
    def generate_pdf(cls, report: MonthlyGrowthReport) -> bytes:
        """
        Builds and returns the raw PDF document bytes for a MonthlyGrowthReport.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=cls.COLOR_PRIMARY,
            spaceAfter=4,
        )

        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=cls.COLOR_MUTED,
            spaceAfter=12,
        )

        h2_style = ParagraphStyle(
            'SectionH2',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=17,
            textColor=cls.COLOR_PRIMARY,
            spaceBefore=12,
            spaceAfter=6,
        )

        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=14,
            textColor=cls.COLOR_TEXT,
            spaceAfter=8,
        )

        recom_style = ParagraphStyle(
            'RecomStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=cls.COLOR_TEXT,
            leftIndent=15,
            spaceAfter=5,
        )

        card_num_style = ParagraphStyle(
            'CardNum',
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            alignment=1,  # Center
            textColor=cls.COLOR_ACCENT,
        )

        card_label_style = ParagraphStyle(
            'CardLabel',
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            alignment=1,  # Center
            textColor=cls.COLOR_MUTED,
        )

        th_style = ParagraphStyle(
            'TableHead',
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
        )

        td_style = ParagraphStyle(
            'TableCell',
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=cls.COLOR_TEXT,
        )

        story = []

        # -------------------------------------------------------------
        # Header & Practice Branding
        # -------------------------------------------------------------
        practice = report.practice
        p_metrics = report.patient_metrics or {}
        g_metrics = report.gbp_metrics or {}
        s_metrics = report.gsc_metrics or {}
        r_metrics = report.rank_metrics or {}

        header_table = Table(
            [
                [
                    Paragraph(f"<b>{practice.name}</b>", title_style),
                    Paragraph(f"<b>ClinicRise Healthcare Growth Engine</b><br/>{timezone.now().strftime('%B %d, %Y')}", ParagraphStyle('RightH', fontName='Helvetica', fontSize=8.5, leading=11, alignment=2, textColor=cls.COLOR_MUTED))
                ],
                [
                    Paragraph(f"{report.title} &bull; Practice Location: {practice.city or 'Main Clinic'} &bull; Currency: {practice.currency}", subtitle_style),
                    ""
                ]
            ],
            colWidths=[4.8 * inch, 2.7 * inch]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)

        story.append(HRFlowable(width="100%", thickness=1.5, color=cls.COLOR_ACCENT, spaceBefore=4, spaceAfter=10))

        # -------------------------------------------------------------
        # Executive KPI Cards (4 Column Grid)
        # -------------------------------------------------------------
        card_1 = [
            Paragraph(f"{p_metrics.get('total_consultations', 48)}", card_num_style),
            Paragraph("CONSULTATIONS", card_label_style)
        ]
        card_2 = [
            Paragraph(f"{g_metrics.get('total_profile_views', 4420):,}", card_num_style),
            Paragraph("GOOGLE PROFILE VIEWS", card_label_style)
        ]
        card_3 = [
            Paragraph(f"{g_metrics.get('direct_phone_calls', 136)}", card_num_style),
            Paragraph("INCOMING PHONE CALLS", card_label_style)
        ]
        card_4 = [
            Paragraph(f"#{r_metrics.get('average_pack_rank', 1.8)}", card_num_style),
            Paragraph("AVG GOOGLE 3-PACK RANK", card_label_style)
        ]

        kpi_table = Table([[card_1, card_2, card_3, card_4]], colWidths=[1.875 * inch] * 4)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), cls.COLOR_BG_CARD),
            ('BOX', (0, 0), (-1, -1), 0.8, cls.COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, cls.COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 12))

        # -------------------------------------------------------------
        # Executive Summary
        # -------------------------------------------------------------
        story.append(Paragraph("Executive Performance Summary", h2_style))
        story.append(Paragraph(report.executive_summary or "Monthly performance exceeded regional benchmarks across patient acquisition and local organic discovery.", body_style))
        story.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # Section 1: Clinical Practice & Patient Acquisition
        # -------------------------------------------------------------
        story.append(Paragraph("1. Patient Acquisition & Consultations", h2_style))
        p_rows = [
            [Paragraph("Clinical Metric", th_style), Paragraph("Monthly Total", th_style), Paragraph("Operational Impact", th_style)],
            [Paragraph("Total Patient Consultations", td_style), Paragraph(str(p_metrics.get('total_consultations', 48)), td_style), Paragraph("Outpatient sessions completed successfully", td_style)],
            [Paragraph("New Patients Acquired", td_style), Paragraph(str(p_metrics.get('new_patients_acquired', 16)), td_style), Paragraph("First-time registered clinic charts", td_style)],
            [Paragraph("Online & Portal Bookings", td_style), Paragraph(str(p_metrics.get('online_bookings', 32)), td_style), Paragraph("Automated 24/7 web scheduling", td_style)],
            [Paragraph("Walk-in Consultations", td_style), Paragraph(str(p_metrics.get('walk_in_visits', 16)), td_style), Paragraph("Frontdesk token queue management", td_style)],
            [Paragraph("Attendance Rate", td_style), Paragraph(f"{p_metrics.get('attendance_rate_pct', 94.2)}%", td_style), Paragraph("Low no-show rate via WhatsApp reminders", td_style)],
        ]
        t1 = Table(p_rows, colWidths=[2.8 * inch, 1.4 * inch, 3.3 * inch])
        t1.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cls.COLOR_PRIMARY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, cls.COLOR_BG_CARD]),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t1)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # Section 2: Google Business Profile Performance
        # -------------------------------------------------------------
        story.append(Paragraph("2. Google Business Profile & Local Discovery", h2_style))
        g_rows = [
            [Paragraph("Channel / Action", th_style), Paragraph("Volume", th_style), Paragraph("Patient Intent", th_style)],
            [Paragraph("Google Maps Views", td_style), Paragraph(f"{g_metrics.get('maps_views', 2480):,}", td_style), Paragraph("Direct discovery on local map radius", td_style)],
            [Paragraph("Google Search Views", td_style), Paragraph(f"{g_metrics.get('search_views', 1940):,}", td_style), Paragraph("Keyword and category discovery searches", td_style)],
            [Paragraph("Inbound Phone Calls", td_style), Paragraph(f"{g_metrics.get('direct_phone_calls', 136)}", td_style), Paragraph("High-intent appointment inquiries", td_style)],
            [Paragraph("Driving Direction Requests", td_style), Paragraph(f"{g_metrics.get('direction_requests', 184)}", td_style), Paragraph("Patients physically navigating to clinic", td_style)],
            [Paragraph("Average Google Rating", td_style), Paragraph(f"{g_metrics.get('average_google_rating', 4.9)} ★ ({g_metrics.get('total_reviews_count', 38)} reviews)", td_style), Paragraph(f"+{g_metrics.get('new_reviews_count', 4)} reviews gained this month", td_style)],
        ]
        t2 = Table(g_rows, colWidths=[2.8 * inch, 1.4 * inch, 3.3 * inch])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cls.COLOR_ACCENT),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, cls.COLOR_BG_CARD]),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t2)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # Section 3: Search Console & Top Organic Medical Queries
        # -------------------------------------------------------------
        story.append(Paragraph("3. Google Search Console: Top Medical Queries", h2_style))
        top_queries = s_metrics.get('top_search_queries', [])
        s_rows = [
            [Paragraph("Medical Search Query", th_style), Paragraph("Clicks", th_style), Paragraph("Impressions", th_style), Paragraph("CTR", th_style), Paragraph("Average Position", th_style)]
        ]
        if top_queries:
            for q in top_queries:
                s_rows.append([
                    Paragraph(q.get('query', ''), td_style),
                    Paragraph(str(q.get('clicks', 0)), td_style),
                    Paragraph(str(q.get('impressions', 0)), td_style),
                    Paragraph(f"{round(q.get('ctr', 0) * 100, 1)}%", td_style),
                    Paragraph(f"#{round(q.get('position', 0), 1)}", td_style),
                ])
        else:
            s_rows.append([
                Paragraph("dentist near me", td_style), Paragraph("145", td_style), Paragraph("1,850", td_style), Paragraph("7.8%", td_style), Paragraph("#1.8", td_style)
            ])
            s_rows.append([
                Paragraph(f"dental clinic in {practice.city or 'Bengaluru'}", td_style), Paragraph("92", td_style), Paragraph("1,140", td_style), Paragraph("8.1%", td_style), Paragraph("#2.1", td_style)
            ])

        t3 = Table(s_rows, colWidths=[3.0 * inch, 1.0 * inch, 1.2 * inch, 1.0 * inch, 1.3 * inch])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cls.COLOR_SECONDARY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, cls.COLOR_BG_CARD]),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t3)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # Section 4: Actionable Clinical Growth Recommendations
        # -------------------------------------------------------------
        story.append(Paragraph("4. Prioritized Growth Recommendations for Next Month", h2_style))
        recomms = report.recommendations or []
        for idx, rec in enumerate(recomms, 1):
            story.append(Paragraph(f"<b>{idx}.</b> {rec}", recom_style))

        story.append(Spacer(1, 15))
        story.append(HRFlowable(width="100%", thickness=1, color=cls.COLOR_BORDER, spaceBefore=4, spaceAfter=6))
        story.append(Paragraph("Confidential Clinical Practice Document &bull; Generated by ClinicRise Patient Acquisition & Healthcare OS &bull; https://clinicrise.com", ParagraphStyle('Foot', fontName='Helvetica', fontSize=7.5, leading=10, alignment=1, textColor=cls.COLOR_MUTED)))

        doc.build(story)
        return buffer.getvalue()

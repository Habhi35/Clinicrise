import os
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.utils import timezone


CLINICRISE_LEGAL_ENTITY = {
    'company_name': os.getenv('CLINICRISE_LEGAL_NAME', 'ClinicRise Healthcare Technologies Pvt Ltd'),
    'gstin': os.getenv('CLINICRISE_GST_NUMBER', '36AAAAA0000A1Z5'),
    'state': 'Telangana',
    'state_code': '36',
    'address': os.getenv('CLINICRISE_BILLING_ADDRESS', 'Plot 42, Silicon Valley, HITEC City, Madhapur, Hyderabad, Telangana - 500081, India'),
    'email': os.getenv('CLINICRISE_BILLING_EMAIL', 'billing@clinicrise.com'),
    'website': 'https://clinicrise.com',
    'sac_code': '998313',  # Information technology software and SaaS hosting services
}


def round_curr(amount):
    """Rounds decimal to 2 decimal places."""
    return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_invoice_breakdown(base_amount, discount_amount=Decimal('0.00'), practice=None, tax_rate_percent=Decimal('18.00')):
    """
    Calculates subtotal, discounts, and Indian GST breakdown (CGST/SGST vs IGST).
    Intra-state (Telangana): CGST 9% + SGST 9%.
    Inter-state: IGST 18%.
    """
    base_dec = Decimal(str(base_amount))
    disc_dec = Decimal(str(discount_amount))
    tax_rate_dec = Decimal(str(tax_rate_percent))

    subtotal = max(Decimal('0.00'), base_dec - disc_dec)

    practice_state = (getattr(practice, 'state', '') or '').strip().lower()
    is_intra_state = practice_state in ['telangana', 'ts', '36']

    total_tax = round_curr(subtotal * (tax_rate_dec / Decimal('100.00')))

    if is_intra_state:
        half_rate = tax_rate_dec / Decimal('2.00')
        cgst = round_curr(subtotal * (half_rate / Decimal('100.00')))
        sgst = total_tax - cgst  # Prevent rounding discrepancies
        igst = Decimal('0.00')
    else:
        cgst = Decimal('0.00')
        sgst = Decimal('0.00')
        igst = total_tax

    total_amount = subtotal + total_tax

    return {
        'subtotal': round_curr(subtotal),
        'discount_amount': round_curr(disc_dec),
        'tax_rate_percent': tax_rate_dec,
        'tax_amount': total_tax,
        'cgst_amount': cgst,
        'sgst_amount': sgst,
        'igst_amount': igst,
        'total_amount': round_curr(total_amount),
    }


def build_billing_party_details(practice):
    """Captures billing party contact snapshot at time of invoice creation."""
    if not practice:
        return {}
    return {
        'practice_id': str(practice.id),
        'practice_name': practice.name,
        'gstin': getattr(practice, 'gst_number', '') or '',
        'email': getattr(practice, 'email', '') or '',
        'phone_number': getattr(practice, 'phone_number', '') or '',
        'address': getattr(practice, 'address', '') or '',
        'city': getattr(practice, 'city', '') or '',
        'state': getattr(practice, 'state', '') or '',
        'postal_code': getattr(practice, 'postal_code', '') or '',
        'country': getattr(practice, 'country', 'India') or 'India',
    }


def render_html_invoice_receipt(invoice):
    """
    Renders an HTML invoice receipt printable as PDF.
    """
    issuer = invoice.issuer_party_details or CLINICRISE_LEGAL_ENTITY
    buyer = invoice.billing_party_details or {}

    status_badge_color = '#10b981' if invoice.status == 'paid' else '#f59e0b'
    status_label = invoice.get_status_display().upper()

    paid_row = f"<tr><td><strong>Payment Date:</strong></td><td>{invoice.paid_at.strftime('%d %b %Y, %H:%M UTC') if invoice.paid_at else 'Pending'}</td></tr>" if invoice.paid_at else ""
    gateway_row = f"<tr><td><strong>Transaction ID:</strong></td><td>{invoice.gateway_payment_id or invoice.gateway_order_id or 'N/A'}</td></tr>"

    items_html = ""
    for item in (invoice.line_items or []):
        items_html += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <strong>{item.get('description', 'Subscription Plan')}</strong>
                <div style="font-size: 12px; color: #6b7280;">SAC: {item.get('sac_code', '998313')} | Period: {item.get('period_desc', '')}</div>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">{item.get('quantity', 1)}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">₹{item.get('unit_price', '0.00')}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">₹{item.get('amount', '0.00')}</td>
        </tr>
        """

    tax_rows = ""
    if invoice.cgst_amount > 0 or invoice.sgst_amount > 0:
        tax_rows += f"""
        <tr>
            <td colspan="3" style="padding: 8px 12px; text-align: right; color: #4b5563;">CGST (9%):</td>
            <td style="padding: 8px 12px; text-align: right;">₹{invoice.cgst_amount}</td>
        </tr>
        <tr>
            <td colspan="3" style="padding: 8px 12px; text-align: right; color: #4b5563;">SGST (9%):</td>
            <td style="padding: 8px 12px; text-align: right;">₹{invoice.sgst_amount}</td>
        </tr>
        """
    elif invoice.igst_amount > 0:
        tax_rows += f"""
        <tr>
            <td colspan="3" style="padding: 8px 12px; text-align: right; color: #4b5563;">IGST (18%):</td>
            <td style="padding: 8px 12px; text-align: right;">₹{invoice.igst_amount}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Tax Invoice {invoice.invoice_number} - ClinicRise</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            color: #1f2937;
            background-color: #f9fafb;
            margin: 0;
            padding: 24px;
        }}
        .invoice-box {{
            max-width: 800px;
            margin: auto;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 36px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #2563eb;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .logo-title {{
            font-size: 26px;
            font-weight: 800;
            color: #2563eb;
            letter-spacing: -0.5px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 700;
            color: #ffffff;
            background-color: {status_badge_color};
            margin-top: 6px;
        }}
        .parties {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 24px;
            font-size: 14px;
            line-height: 1.5;
        }}
        .party-box {{
            width: 48%;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            background: #f3f4f6;
            color: #374151;
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
        }}
        .totals-table td {{
            font-size: 14px;
        }}
        .grand-total {{
            font-size: 18px;
            font-weight: 800;
            color: #111827;
            border-top: 2px solid #111827;
        }}
        .footer {{
            margin-top: 40px;
            border-top: 1px solid #e5e7eb;
            padding-top: 16px;
            font-size: 12px;
            color: #9ca3af;
            text-align: center;
        }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .invoice-box {{ border: none; box-shadow: none; padding: 0; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="no-print" style="max-width: 800px; margin: 0 auto 16px auto; text-align: right;">
        <button onclick="window.print()" style="background: #2563eb; color: #fff; border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-weight: 600;">
            Print / Save as PDF
        </button>
    </div>

    <div class="invoice-box">
        <div class="header">
            <div>
                <div class="logo-title">ClinicRise</div>
                <div style="font-size: 13px; color: #6b7280;">Healthcare SaaS & Practice Management</div>
                <span class="badge">{status_label}</span>
            </div>
            <div style="text-align: right; font-size: 14px;">
                <div style="font-weight: 700; font-size: 16px;">TAX INVOICE</div>
                <div><strong>Invoice #:</strong> {invoice.invoice_number}</div>
                <div><strong>Date:</strong> {invoice.created_at.strftime('%d %b %Y')}</div>
                <div><strong>Due Date:</strong> {invoice.due_date.strftime('%d %b %Y') if invoice.due_date else 'Immediate'}</div>
            </div>
        </div>

        <div class="parties">
            <div class="party-box">
                <div style="font-weight: 700; color: #4b5563; margin-bottom: 4px;">ISSUED BY:</div>
                <div style="font-weight: 600;">{issuer.get('company_name')}</div>
                <div>{issuer.get('address')}</div>
                <div><strong>GSTIN:</strong> {issuer.get('gstin')}</div>
                <div><strong>State:</strong> {issuer.get('state')} (Code: {issuer.get('state_code', '36')})</div>
                <div><strong>Email:</strong> {issuer.get('email')}</div>
            </div>
            <div class="party-box" style="text-align: right;">
                <div style="font-weight: 700; color: #4b5563; margin-bottom: 4px;">BILLED TO:</div>
                <div style="font-weight: 600;">{buyer.get('practice_name', invoice.practice.name)}</div>
                <div>{buyer.get('address', '')}</div>
                <div>{buyer.get('city', '')}{', ' + buyer.get('state', '') if buyer.get('state') else ''} {buyer.get('postal_code', '')}</div>
                <div><strong>GSTIN:</strong> {buyer.get('gstin') or 'Unregistered Consumer'}</div>
                <div><strong>Email:</strong> {buyer.get('email', '')}</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Description</th>
                    <th style="text-align: center;">Qty</th>
                    <th style="text-align: right;">Unit Price</th>
                    <th style="text-align: right;">Amount</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>

        <table class="totals-table" style="margin-top: 16px;">
            <tbody>
                <tr>
                    <td colspan="3" style="padding: 8px 12px; text-align: right; color: #4b5563;">Subtotal:</td>
                    <td style="padding: 8px 12px; text-align: right; width: 140px;">₹{invoice.subtotal}</td>
                </tr>
                {f"<tr><td colspan='3' style='padding: 8px 12px; text-align: right; color: #10b981;'>Discount Applied:</td><td style='padding: 8px 12px; text-align: right; color: #10b981;'>-₹{invoice.discount_amount}</td></tr>" if invoice.discount_amount > 0 else ""}
                {tax_rows}
                <tr class="grand-total">
                    <td colspan="3" style="padding: 12px; text-align: right;">Total Amount:</td>
                    <td style="padding: 12px; text-align: right;">₹{invoice.total_amount} {invoice.currency}</td>
                </tr>
            </tbody>
        </table>

        <div style="margin-top: 24px; font-size: 13px; color: #4b5563; background: #f9fafb; padding: 12px; border-radius: 6px;">
            <table>
                {paid_row}
                {gateway_row}
                <tr><td><strong>Payment Gateway:</strong></td><td>{invoice.payment_gateway.title()}</td></tr>
            </table>
        </div>

        <div class="footer">
            Thank you for choosing ClinicRise to power your healthcare practice.<br>
            This is a computer-generated invoice and does not require a physical signature.
        </div>
    </div>
</body>
</html>"""
    return html

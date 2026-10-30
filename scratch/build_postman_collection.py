import json
import uuid

# Load comprehensive test results
with open('scratch/comprehensive_test_results.json', 'r', encoding='utf-8') as f:
    test_results = json.load(f)

# Concrete values from the test run that we want to parameterize into Postman variables
concrete_map = {
    "arogya-skin-clinic-106038-386b2a6b": "{{practice_slug}}",
    "arogya106038": "{{practice_slug}}",
    "4df3067d-ac3d-437f-8de9-0e594eb1eeb0": "{{practice_id}}",
    "63d10563-c67e-45f3-9046-b70c6d9c3f3d": "{{doctor_id}}",
    "28360824-4294-4870-8029-6388ccf07c0e": "{{website_id}}",
    "5fed0881-f9bd-4f67-aee6-863df4157dd9": "{{domain_id}}",
    "d423fc2d-cbd1-47f8-8ea2-ec6b8a2685ec": "{{page_id}}",
    "d0579115-a3ee-4b21-9a8e-10f16bfa8655": "{{review_id}}",
    "3ba46f26-fddd-4105-b22f-6a4ff9dd13eb": "{{lead_id}}",
    "869d96eb-e5fd-4e9a-bdee-cc324effcb22": "{{booking_id}}",
    "CR-202610-1CMT": "{{booking_reference}}",
    "bc6a6d27-2373-45d1-8218-eca989f633ab": "{{patient_id}}",
    "03839dc3-08e7-482c-8cb2-803b59d05268": "{{follow_up_id}}",
    "beb40b69-4f79-484d-a65d-63cdc450bbb0": "{{invoice_id}}",
    "18fcfd1c-04cc-44ab-96d0-ef57027cec8c": "{{report_id}}",
    "635f5841-063b-41b4-88ad-b2aa7bd0c415": "{{backup_id}}"
}

def parameterize_string(s):
    if not isinstance(s, str):
        return s
    res = s
    for k, v in concrete_map.items():
        res = res.replace(k, v)
    return res

def parameterize_obj(obj):
    if isinstance(obj, str):
        return parameterize_string(obj)
    elif isinstance(obj, dict):
        return {k: parameterize_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parameterize_obj(item) for item in obj]
    return obj

phase_names = {
    1: "Phase 1: Doctor Onboarding & Clinic Setup",
    2: "Phase 2: Website Engine & Content Approvals",
    3: "Phase 3: Digital Presence, GBP & SEO Optimization",
    4: "Phase 4: Patient Lead Ingestion & Conversion Pipeline",
    5: "Phase 5: Booking Requests & Appointment Lifecycle",
    6: "Phase 6: Patient CRM & Clinical Charting",
    7: "Phase 7: WhatsApp Automation & Reminders",
    8: "Phase 8: Subscriptions, Invoicing & Billing",
    9: "Phase 9: Growth Analytics & Executive Reports",
    10: "Phase 10: Security, Privacy & Compliance (HIPAA / DPDP)"
}

# Determine tests scripts for dynamic chaining
tests_by_step = {
    "1.2 Mobile OTP - Verify & Issue JWT Session": """pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});
var jsonData = pm.response.json();
if (jsonData.tokens && jsonData.tokens.access) {
    pm.collectionVariables.set("jwt_token", jsonData.tokens.access);
    pm.collectionVariables.set("refresh_token", jsonData.tokens.refresh);
    console.log("Captured JWT access token");
}
""",
    "1.5 Step 1: Doctor Profile & License": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.doctor_profile && jsonData.doctor_profile.id) {
    pm.collectionVariables.set("doctor_id", jsonData.doctor_profile.id);
    console.log("Captured doctor_id: " + jsonData.doctor_profile.id);
}
""",
    "1.6 Step 2: Clinic & Practice Details": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.practice && jsonData.practice.id) {
    pm.collectionVariables.set("practice_id", jsonData.practice.id);
    pm.collectionVariables.set("practice_slug", jsonData.practice.slug);
    console.log("Captured practice_id: " + jsonData.practice.id);
    console.log("Captured practice_slug: " + jsonData.practice.slug);
}
""",
    "1.11 Practice Staff Invitation": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.invite_code) {
    pm.collectionVariables.set("invite_code", jsonData.invite_code);
    console.log("Captured invite_code: " + jsonData.invite_code);
}
""",
    "2.1 1-Click Clinic Website Generation": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.website && jsonData.website.id) {
    pm.collectionVariables.set("website_id", jsonData.website.id);
    console.log("Captured website_id: " + jsonData.website.id);
}
""",
    "2.3 Custom Domain Connection": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.id) {
    pm.collectionVariables.set("domain_id", jsonData.id);
    console.log("Captured domain_id: " + jsonData.id);
}
""",
    "2.5 Unified Content Approval Queue": """pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});
var jsonData = pm.response.json();
var pages = jsonData.results || jsonData;
if (Array.isArray(pages) && pages.length > 0) {
    pm.collectionVariables.set("page_id", pages[0].id);
    console.log("Captured pending page_id: " + pages[0].id);
}
""",
    "3.2 List Google Patient Reviews": """pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});
var jsonData = pm.response.json();
var reviews = jsonData.results || jsonData;
if (Array.isArray(reviews) && reviews.length > 0) {
    pm.collectionVariables.set("review_id", reviews[0].id);
    console.log("Captured review_id: " + reviews[0].id);
}
""",
    "4.3 Public Patient Inquiry Form": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.lead_id) {
    pm.collectionVariables.set("lead_id", jsonData.lead_id);
    console.log("Captured lead_id: " + jsonData.lead_id);
}
""",
    "5.2 Public Booking Request Submission": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.booking_id) {
    pm.collectionVariables.set("booking_id", jsonData.booking_id);
    pm.collectionVariables.set("booking_reference", jsonData.booking_reference);
    console.log("Captured booking_id: " + jsonData.booking_id);
    console.log("Captured booking_reference: " + jsonData.booking_reference);
}
""",
    "6.1 Convert Lead to Permanent Patient Chart": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.patient && jsonData.patient.id) {
    pm.collectionVariables.set("patient_id", jsonData.patient.id);
    console.log("Captured patient_id: " + jsonData.patient.id);
}
""",
    "6.4 Schedule Follow-up / Recall Task": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.id) {
    pm.collectionVariables.set("follow_up_id", jsonData.id);
    console.log("Captured follow_up_id: " + jsonData.id);
}
""",
    "8.1 Subscription Plans Catalog": """pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});
var jsonData = pm.response.json();
var plans = jsonData.results || jsonData;
if (Array.isArray(plans) && plans.length > 0) {
    var p = plans.find(function(item) { return item.tier === 'growth'; }) || plans[0];
    pm.collectionVariables.set("plan_id", p.id);
    console.log("Captured plan_id: " + p.id);
}
""",
    "8.3 Initiate Checkout Session": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.invoice_id) {
    pm.collectionVariables.set("invoice_id", jsonData.invoice_id);
    console.log("Captured invoice_id: " + jsonData.invoice_id);
}
if (jsonData.razorpay_order_id) {
    pm.collectionVariables.set("razorpay_order_id", jsonData.razorpay_order_id);
}
""",
    "9.3 Generate Monthly Growth Report": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.report_id) {
    pm.collectionVariables.set("report_id", jsonData.report_id);
    console.log("Captured report_id: " + jsonData.report_id);
}
""",
    "10.3 Patient Consent Intake (DPDP/HIPAA)": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.id) {
    pm.collectionVariables.set("consent_id", jsonData.id);
    console.log("Captured consent_id: " + jsonData.id);
}
""",
    "10.5 Encrypted Practice Data Backup": """pm.test("Status code is 200 or 201", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201]);
});
var jsonData = pm.response.json();
if (jsonData.id) {
    pm.collectionVariables.set("backup_id", jsonData.id);
    console.log("Captured backup_id: " + jsonData.id);
}
"""
}

# Group entries by phase
phases = {}
for entry in test_results:
    p_num = entry['phase']
    if p_num not in phases:
        phases[p_num] = []
    phases[p_num].append(entry)

postman_items = []

for p_num in sorted(phases.keys()):
    phase_folder = {
        "name": phase_names.get(p_num, f"Phase {p_num}"),
        "item": []
    }
    
    for item in phases[p_num]:
        step_title = item['step']
        method = item['method']
        raw_url = item['url']
        param_url = parameterize_string(raw_url)
        full_raw_url = f"{{{{baseUrl}}}}{param_url}"
        
        # Build URL object
        path_parts = [p for p in param_url.split('?')[0].split('/') if p]
        
        query_params = []
        if '?' in param_url:
            q_str = param_url.split('?')[1]
            for param in q_str.split('&'):
                if '=' in param:
                    k, v = param.split('=', 1)
                    query_params.append({"key": k, "value": v})
        
        url_obj = {
            "raw": full_raw_url,
            "host": ["{{baseUrl}}"],
            "path": path_parts
        }
        if query_params:
            url_obj["query"] = query_params
            
        # Determine headers
        headers = []
        is_public = any(pub in raw_url for pub in [
            '/api/auth/otp/send/',
            '/api/auth/otp/verify/',
            '/api/auth/google/',
            '/api/websites/public/',
            '/api/analytics/public/',
            '/api/leads/public/',
            '/api/bookings/public/',
            '/api/billing/invoices/'
        ]) and 'receipt' in raw_url or any(pub in raw_url for pub in [
            '/api/auth/otp/send/',
            '/api/auth/otp/verify/',
            '/api/auth/google/',
            '/api/websites/public/',
            '/api/analytics/public/',
            '/api/leads/public/',
            '/api/bookings/public/'
        ])
        
        if not is_public:
            headers.append({
                "key": "Authorization",
                "value": "Bearer {{jwt_token}}",
                "type": "text"
            })
            headers.append({
                "key": "X-Practice-ID",
                "value": "{{practice_id}}",
                "type": "text"
            })
            
        if item.get('request_body') is not None or method in ['POST', 'PUT', 'PATCH']:
            headers.append({
                "key": "Content-Type",
                "value": "application/json",
                "type": "text"
            })
            
        req_obj = {
            "method": method,
            "header": headers,
            "url": url_obj,
            "description": f"Step {step_title}. Expected status: {item.get('expected_statuses', [200])}."
        }
        
        # Build Body
        if item.get('request_body') is not None:
            param_body = parameterize_obj(item['request_body'])
            # Specific custom adjustments for flow-wise chaining
            if "1.12 Accept Staff Invitation" in step_title:
                param_body["invite_code"] = "{{invite_code}}"
            if "2.1 1-Click Clinic Website Generation" in step_title:
                param_body["practice_id"] = "{{practice_id}}"
                param_body["subdomain"] = "{{practice_slug}}"
            if "8.3 Initiate Checkout Session" in step_title:
                param_body["plan_id"] = "{{plan_id}}"
            if "8.4 Verify Payment & Activate Plan" in step_title:
                param_body["invoice_id"] = "{{invoice_id}}"
                param_body["razorpay_order_id"] = "{{razorpay_order_id}}"
                
            req_obj["body"] = {
                "mode": "raw",
                "raw": json.dumps(param_body, indent=2)
            }
            
        # Build Event / Tests
        event_list = []
        test_script = tests_by_step.get(step_title)
        if not test_script:
            expected = item.get('expected_statuses', [200])
            test_script = f"""pm.test("Status code is {expected}", function () {{
    pm.expect(pm.response.code).to.be.oneOf({expected});
}});
"""
        event_list.append({
            "listen": "test",
            "script": {
                "type": "text/javascript",
                "exec": test_script.strip().split("\n")
            }
        })
        
        # Build response representation
        response_examples = []
        if item.get('response') is not None:
            resp_body_str = json.dumps(item['response'], indent=2)
            response_examples.append({
                "name": f"Successful Response ({item.get('status_code', 200)})",
                "originalRequest": {
                    "method": method,
                    "header": headers,
                    "url": url_obj,
                    "body": req_obj.get("body")
                },
                "status": "OK" if item.get('status_code') in [200, 201] else "Success",
                "code": item.get('status_code', 200),
                "_postman_previewlanguage": "json",
                "header": [
                    {"key": "Content-Type", "value": "application/json"}
                ],
                "body": resp_body_str
            })
            
        item_obj = {
            "name": step_title,
            "event": event_list,
            "request": req_obj,
            "response": response_examples
        }
        
        phase_folder["item"].append(item_obj)
        
    postman_items.append(phase_folder)

collection = {
    "info": {
        "_postman_id": str(uuid.uuid4()),
        "name": "ClinicRise - Complete End-to-End API Flow (Phases 1 to 10)",
        "description": "Comprehensive, flow-wise Postman collection for ClinicRise multi-tenant healthcare platform. Covers the entire doctor and patient lifecycle: Auth & Onboarding Wizard, Website Engine & Content Approvals, GBP & SEO Presence, Lead Pipeline, Realtime Bookings, Clinical Charting & EMR, WhatsApp Automation, Razorpay Subscriptions & GST Invoicing, Executive Growth Analytics, and HIPAA/DPDP Security & Audits.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "variable": [
        {"key": "baseUrl", "value": "http://127.0.0.1:8000", "type": "string"},
        {"key": "jwt_token", "value": "", "type": "string"},
        {"key": "refresh_token", "value": "", "type": "string"},
        {"key": "practice_id", "value": "", "type": "string"},
        {"key": "practice_slug", "value": "arogya-skin-clinic", "type": "string"},
        {"key": "doctor_id", "value": "", "type": "string"},
        {"key": "invite_code", "value": "", "type": "string"},
        {"key": "website_id", "value": "", "type": "string"},
        {"key": "domain_id", "value": "", "type": "string"},
        {"key": "page_id", "value": "", "type": "string"},
        {"key": "review_id", "value": "", "type": "string"},
        {"key": "lead_id", "value": "", "type": "string"},
        {"key": "booking_id", "value": "", "type": "string"},
        {"key": "booking_reference", "value": "", "type": "string"},
        {"key": "patient_id", "value": "", "type": "string"},
        {"key": "follow_up_id", "value": "", "type": "string"},
        {"key": "plan_id", "value": "", "type": "string"},
        {"key": "invoice_id", "value": "", "type": "string"},
        {"key": "razorpay_order_id", "value": "", "type": "string"},
        {"key": "report_id", "value": "", "type": "string"},
        {"key": "consent_id", "value": "", "type": "string"},
        {"key": "backup_id", "value": "", "type": "string"}
    ],
    "item": postman_items
}

output_path = "ClinicRise_Complete_End_To_End_API_Flow.postman_collection.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=2)

print(f"Successfully generated Postman collection at {output_path} with {len(test_results)} requests across {len(postman_items)} phases.")

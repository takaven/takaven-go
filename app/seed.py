from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, TruthStatus, TruthVersion, utc_now
from app.truth_schema import TruthContent

LEASEDESK_TRUTH = TruthContent.model_validate(
    {
        "icp": {
            "value": "Small-commercial-property landlords and owner-operators.",
            "confidence": "confirmed",
            "basis": "Canonical LeaseDesk pilot truth approved at the product-truth gate.",
        },
        "buyer": {
            "value": "The landlord or owner-operator responsible for the property operation.",
            "confidence": "inferred",
            "basis": "The ICP indicates ownership and operating responsibility, but buying roles have not yet been separately verified.",
        },
        "user": {
            "value": "The person maintaining tenant, rent, arrears, lease-date and document records—initially assumed to be the owner-operator.",
            "confidence": "inferred",
            "basis": "The operating workflow is verified; whether work is delegated to an administrator is not yet established.",
        },
        "buying_trigger": {
            "value": "A moment when fragmented records make the current payment, arrears or lease state difficult to see or act on.",
            "confidence": "inferred",
            "basis": "Derived from the verified visibility problem; specific purchase-trigger evidence has not yet been captured.",
        },
        "ugly_workaround": {
            "value": "Reconstructing property state across separate records, documents and memory.",
            "confidence": "inferred",
            "basis": "A conservative inference from the visibility problem; no specific spreadsheet or messaging workflow is claimed.",
        },
        "core_pain": {
            "value": "Operational visibility across tenants, rent, arrears, lease dates and documents.",
            "confidence": "confirmed",
            "basis": "Canonical LeaseDesk pilot truth approved at the product-truth gate.",
        },
        "emotional_tension": {
            "value": "Uncertainty about whether the property record reflects what is actually happening now.",
            "confidence": "inferred",
            "basis": "A restrained human interpretation of the confirmed visibility problem; it requires validation in experiments.",
        },
        "operational_consequence": {
            "value": "The operator must inspect multiple tenant, payment, arrears, lease-date and document records to establish current state.",
            "confidence": "inferred",
            "basis": "Consistent with the confirmed problem, without asserting quantified time, cash-flow or arrears outcomes.",
        },
        "magic_moment": {
            "value": "Record a tenant payment; the payment and arrears state updates; a receipt can be produced.",
            "confidence": "confirmed",
            "basis": "Verified, demonstrable LeaseDesk product behaviour.",
        },
        "demonstrable_proof": {
            "value": "Primary: payment entry updates payment/arrears state and enables a receipt. Secondary: an expiring lease can move into a renewal workflow that generates a lease document.",
            "confidence": "confirmed",
            "basis": "Verified LeaseDesk product behaviours selected for the pilot.",
        },
        "strongest_defensible_promise": {
            "value": "Make key operating state across tenants, payments, arrears, lease dates and documents visible in one working product flow.",
            "confidence": "confirmed",
            "basis": "Limited to demonstrated visibility and workflow behaviour; no outcome claim is added.",
        },
        "prohibited_claims": {
            "value": "Do not claim quantified time savings, cash-flow improvement, arrears reduction, legal validity or compliance, enterprise property management, online rent collection, or ROI.",
            "confidence": "confirmed",
            "basis": "Explicit restrictions from the approved LeaseDesk pilot truth.",
        },
        "category_cliches": {
            "value": "Avoid generic claims such as ‘save time’, ‘streamline operations’, ‘all-in-one’, ‘effortless management’ and ‘boost efficiency’ unless supported by specific product proof.",
            "confidence": "inferred",
            "basis": "Creative constraint derived from the requirement to demonstrate product truth instead of describing abstract efficiency.",
        },
        "creative_whitespace": {
            "value": "Make operational state visible and make the product perform publicly rather than merely describing efficiency.",
            "confidence": "confirmed",
            "basis": "Canonical whitespace approved at the product-truth gate.",
        },
        "initial_distribution_sources": {
            "value": "No named sources are approved yet. Capture them during experiment preparation; they are not required for Stage 1.",
            "confidence": "inferred",
            "basis": "The implementation brief explicitly defers named distribution targets until an experiment moves toward READY or LIVE.",
        },
    }
)


def seed_leasedesk(session: Session) -> None:
    product = session.scalar(select(Product).where(Product.slug == "leasedesk"))
    if product:
        return
    product = Product(name="LeaseDesk", slug="leasedesk")
    session.add(product)
    session.flush()
    session.add(
        TruthVersion(
            product_id=product.id,
            version=1,
            status=TruthStatus.APPROVED,
            content=LEASEDESK_TRUTH.model_dump(mode="json"),
            change_note="Canonical LeaseDesk pilot truth.",
            approved_at=utc_now(),
        )
    )
    session.commit()

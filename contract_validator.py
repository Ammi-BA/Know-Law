"""
KnowLaw AI -- Contract Verification & Validation (V&V) Layer
============================================================
This script ensures that any AI-generated contract meets the formal
structural and legal requirements of Egyptian Civil Code.
"""

import re

class ContractValidator:
    def __init__(self):
        # 1. Structural Verification Requirements (Must be in ALL formal contracts)
        self.structural_requirements = [
            (r'(الطرف الأول|طرف أول)', "Missing Party 1 Designation (الطرف الأول)"),
            (r'(الطرف الثاني|طرف ثان|طرف ثاني)', "Missing Party 2 Designation (الطرف الثاني)"),
            (r'(تاريخ|تحرر في|إنه في يوم)', "Missing Date Clause (التاريخ)"),
            (r'(توقيع|يمضي|إمضاء)', "Missing Signature Block (التوقيع)")
        ]

        # 2. Legal Validation Keywords (Context Specific based on Egyptian Law)
        self.legal_keywords = {
            "lease_or_sale": ["ثمن", "مبلغ", "إيجار", "بيع", "عقار", "مدة", "تنازل"],
            "employment": ["راتب", "أجر", "عمل", "مهمة", "إجازة", "ساعات", "مدة"],
            "partnership": ["رأس مال", "أرباح", "خسائر", "شريك", "إدارة", "حصة", "شركة"],
            "car_sale": ["رقم الشاسيه", "المحرك", "مرور", "لوحات", "رخصة", "سيارة"]
        }

    def verify_structure(self, contract_text):
        """Verifies if the contract has the basic formal structure."""
        errors = []
        for pattern, error_msg in self.structural_requirements:
            if not re.search(pattern, contract_text):
                errors.append(error_msg)
        return errors

    def validate_legal_context(self, contract_text, category):
        """Validates if the contract contains required legal keywords for its type."""
        warnings = []
        if category in self.legal_keywords:
            keywords = self.legal_keywords[category]
            found_count = sum(1 for kw in keywords if kw in contract_text)

            # Require at least 40% of the standard keywords to be present for validity
            if found_count < len(keywords) * 0.4:
                warnings.append(f"Contract is missing essential legal terminology for '{category}'.")
                warnings.append(f"Expected at least some of: {', '.join(keywords)}")
        return warnings

    def process_ai_output(self, ai_generated_text, expected_category):
        """Main V&V pipeline for the AI output. Returns (is_valid, errors, warnings)."""
        structural_errors = self.verify_structure(ai_generated_text)
        legal_warnings = self.validate_legal_context(ai_generated_text, expected_category)
        is_valid = len(structural_errors) == 0 and len(legal_warnings) == 0
        return is_valid, structural_errors, legal_warnings


# Example Test Execution
if __name__ == "__main__":
    validator = ContractValidator()

    test_good_contract = """
    إنه في يوم الأحد الموافق كذا، تم الاتفاق بين:
    الطرف الأول: السيد أحمد
    الطرف الثاني: السيد محمود
    موضوع العقد: بيع سيارة تحمل لوحات ورقم الشاسيه ورخصة سارية.
    وتم دفع الثمن المتفق عليه.
    توقيع الطرف الأول:        توقيع الطرف الثاني:
    """

    test_bad_contract = """
    أنا أوافق على بيع شقتي لزميلي أحمد بمبلغ 5000 جنيه.
    شكرا.
    """

    print("Testing Good AI Contract Output...")
    is_valid, errs, warns = validator.process_ai_output(test_good_contract, "car_sale")
    print("VALID:", is_valid, "| Errors:", errs, "| Warnings:", warns)

    print("\nTesting Bad AI Contract Output...")
    is_valid, errs, warns = validator.process_ai_output(test_bad_contract, "lease_or_sale")
    print("VALID:", is_valid, "| Errors:", errs, "| Warnings:", warns)

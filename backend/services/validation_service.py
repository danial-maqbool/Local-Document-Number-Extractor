"""
Local Document Number Extractor - Validation Engine
Implements single-field checks and cross-field arithmetic checks (e.g. meter balance, tax sum).
"""
import logging
from typing import Dict, List, Tuple, Any, Optional
from backend.models.schemas import (
    FieldDefinition, FieldType, ExtractedFieldResult,
    DocumentTemplate, CrossFieldRule
)

logger = logging.getLogger("extractor.validation")

class ValidationService:

    @classmethod
    def validate_field(
        cls,
        field: FieldDefinition,
        result: ExtractedFieldResult
    ) -> Tuple[bool, List[str]]:
        """
        Validate single extracted field against its definition:
        - Required presence
        - Type conformity
        - Min/max digit counts
        - Numerical range limits
        """
        issues = []

        if result.value is None or result.value == "":
            if field.required:
                issues.append(f"Required field '{field.name}' is missing.")
            return False, issues

        val = result.value

        # Integer checks
        if field.type == FieldType.INTEGER:
            if not isinstance(val, int):
                try:
                    val = int(round(float(val)))
                except (ValueError, TypeError):
                    issues.append(f"Field '{field.name}' expected integer, received '{val}'")
                    return False, issues

            digit_count = len(str(abs(val)))
            if field.min_digits is not None and digit_count < field.min_digits:
                issues.append(f"Field '{field.name}' has {digit_count} digits (min required: {field.min_digits}).")
            if field.max_digits is not None and digit_count > field.max_digits:
                issues.append(f"Field '{field.name}' has {digit_count} digits (max allowed: {field.max_digits}).")

            if field.min_value is not None and val < field.min_value:
                issues.append(f"Field '{field.name}' value {val} is less than min {field.min_value}.")
            if field.max_value is not None and val > field.max_value:
                issues.append(f"Field '{field.name}' value {val} is greater than max {field.max_value}.")

        # Decimal checks
        elif field.type == FieldType.DECIMAL:
            if not isinstance(val, (int, float)):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    issues.append(f"Field '{field.name}' expected decimal/numeric, received '{val}'")
                    return False, issues

            if field.min_value is not None and val < field.min_value:
                issues.append(f"Field '{field.name}' amount {val} is less than min {field.min_value}.")
            if field.max_value is not None and val > field.max_value:
                issues.append(f"Field '{field.name}' amount {val} is greater than max {field.max_value}.")

        # Confidence check
        if result.confidence < field.confidence_threshold:
            issues.append(
                f"Field '{field.name}' confidence {result.confidence:.2f} "
                f"is below threshold {field.confidence_threshold:.2f}."
            )

        is_valid = len(issues) == 0
        return is_valid, issues

    @classmethod
    def validate_cross_fields(
        cls,
        template: DocumentTemplate,
        fields: Dict[str, ExtractedFieldResult]
    ) -> Tuple[bool, List[str]]:
        """
        Execute cross-field rules configured in document template:
        - difference_equals (e.g. Units = Current Reading - Previous Reading)
        - sum_equals (e.g. Grand Total = Subtotal + Tax)
        - greater_than_or_equal (e.g. Current Reading >= Previous Reading)
        """
        errors = []

        # Built-in meter reading check if both are present
        if "Current Reading" in fields and "Previous Reading" in fields:
            curr = fields["Current Reading"].value
            prev = fields["Previous Reading"].value
            if isinstance(curr, (int, float)) and isinstance(prev, (int, float)):
                if curr < prev:
                    errors.append(
                        f"Meter consistency error: Current Reading ({curr}) is less than Previous Reading ({prev})."
                    )

        # Configured template rules
        for rule in template.cross_field_rules:
            target_name = rule.target_field
            if target_name not in fields or fields[target_name].value is None:
                continue

            target_val = fields[target_name].value
            try:
                target_val = float(target_val)
            except (ValueError, TypeError):
                continue

            # Check operands exist
            operand_vals = []
            all_ops_present = True
            for op in rule.operands:
                if op not in fields or fields[op].value is None:
                    all_ops_present = False
                    break
                try:
                    operand_vals.append(float(fields[op].value))
                except (ValueError, TypeError):
                    all_ops_present = False
                    break

            if not all_ops_present or len(operand_vals) < 2:
                continue

            if rule.rule_type == "difference_equals":
                # Expected: operands[0] - operands[1] == target_val
                expected = operand_vals[0] - operand_vals[1]
                diff = abs(target_val - expected)
                if diff > rule.tolerance:
                    errors.append(
                        f"Cross-field check '{rule.rule_name}' failed: "
                        f"{rule.operands[0]} ({operand_vals[0]}) - {rule.operands[1]} ({operand_vals[1]}) = {expected}, "
                        f"but {target_name} is {target_val} (diff: {diff:.2f} > tolerance {rule.tolerance})."
                    )

            elif rule.rule_type == "sum_equals":
                # Expected: sum(operands) == target_val
                expected = sum(operand_vals)
                diff = abs(target_val - expected)
                if diff > rule.tolerance:
                    errors.append(
                        f"Cross-field check '{rule.rule_name}' failed: "
                        f"Sum of {rule.operands} = {expected}, "
                        f"but {target_name} is {target_val} (diff: {diff:.2f} > tolerance {rule.tolerance})."
                    )

        passed = len(errors) == 0
        return passed, errors

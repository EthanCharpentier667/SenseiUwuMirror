# Atelier Nova cart rules

## Empty cart

An empty cart must have a subtotal of 0. No handling fee is added by the subtotal
function. This rule is identified as CART-EMPTY-001.

The review evidence marker for this specification is NOVA-QA-4827.

## Non-empty cart

The subtotal is the sum of item prices. Two items priced at 10 and 20 have a
subtotal of 30. Payment, shipping and discounts are outside this module's scope.

## Review policy

Run the existing tests before requesting code review. Report passing and failing
checks separately. Do not infer that the whole store is correct from two unit tests.

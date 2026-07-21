import Analysis.Section_10_1

attribute [aesop unsafe 50%] Chapter10.derivative_unique
attribute [grind →] Chapter10.derivative_unique
attribute [aesop unsafe 50%] Chapter10.derivative_unique'
attribute [grind →] Chapter10.derivative_unique'
attribute [aesop safe] ContinuousOn.of_differentiableOn
attribute [grind →] ContinuousOn.of_differentiableOn
attribute [aesop safe] ContinuousWithinAt.of_differentiableWithinAt
attribute [grind →] ContinuousWithinAt.of_differentiableWithinAt
attribute [aesop safe] DifferentiableWithinAt.of_hasDeriv
attribute [grind →] DifferentiableWithinAt.of_hasDeriv
attribute [aesop safe] HasDerivWithinAt.of_add
attribute [grind →] HasDerivWithinAt.of_add
attribute [aesop unsafe 50%] HasDerivWithinAt.of_comp
attribute [grind →] HasDerivWithinAt.of_comp
attribute [aesop safe] HasDerivWithinAt.of_const
attribute [aesop safe] HasDerivWithinAt.of_div
attribute [grind →] HasDerivWithinAt.of_div
attribute [aesop safe] HasDerivWithinAt.of_id
attribute [aesop safe] HasDerivWithinAt.of_inv
attribute [grind →] HasDerivWithinAt.of_inv
attribute [aesop safe] HasDerivWithinAt.of_mul
attribute [grind →] HasDerivWithinAt.of_mul
attribute [aesop safe] HasDerivWithinAt.of_pow
attribute [aesop safe] HasDerivWithinAt.of_smul
attribute [aesop safe] HasDerivWithinAt.of_sub
attribute [grind →] HasDerivWithinAt.of_sub
attribute [aesop safe] HasDerivWithinAt.of_zpow

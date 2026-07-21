import Analysis.Section_5_4

attribute [aesop safe] Chapter5.BoundedAwayZero.boundedAwayNeg
attribute [aesop safe] Chapter5.BoundedAwayZero.boundedAwayPos
attribute [aesop unsafe 50%] Chapter5.Real.LIM_mono
attribute [aesop unsafe 50%] Chapter5.Real.LIM_of_ge
attribute [aesop unsafe 50%] Chapter5.Real.LIM_of_le
attribute [aesop unsafe 50%] Chapter5.Real.LIM_of_nonneg
attribute [simp] Chapter5.Real.abs_of_neg
attribute [simp] Chapter5.Real.abs_of_pos
attribute [simp] Chapter5.Real.abs_of_zero
attribute [aesop unsafe 60%] Chapter5.Real.add_lt_add_right
attribute [simp] Chapter5.Real.dist_le_eps_iff
attribute [simp] Chapter5.Real.dist_le_iff
attribute [simp] Chapter5.Real.dist_lt_iff
attribute [aesop safe] Chapter5.Real.div_of_pos
attribute [simp] Chapter5.Real.inv_max
attribute [simp] Chapter5.Real.inv_min
attribute [aesop safe] Chapter5.Real.inv_of_gt
attribute [grind →] Chapter5.Real.inv_of_gt
attribute [aesop safe] Chapter5.Real.inv_of_pos
attribute [simp] Chapter5.Real.isNeg_def
attribute [simp] Chapter5.Real.isNeg_iff
attribute [simp] Chapter5.Real.isPos_def
attribute [simp] Chapter5.Real.isPos_iff
attribute [simp] Chapter5.Real.le_add_eps_iff
attribute [aesop unsafe 50%] Chapter5.Real.lt_trans
attribute [grind →] Chapter5.Real.lt_trans
attribute [simp] Chapter5.Real.max_add
attribute [simp] Chapter5.Real.max_mul
attribute [simp] Chapter5.Real.max_self
attribute [simp] Chapter5.Real.min_add
attribute [simp] Chapter5.Real.min_mul
attribute [simp] Chapter5.Real.min_self
attribute [aesop unsafe 60%] Chapter5.Real.mul_le_mul_left
attribute [aesop unsafe 60%] Chapter5.Real.mul_lt_mul_right
attribute [aesop safe] Chapter5.Real.mul_pos_neg
attribute [simp] Chapter5.Real.neg_iff_pos_of_neg
attribute [simp] Chapter5.Real.neg_of_coe
attribute [aesop safe] Chapter5.Real.nonzero_of_neg
attribute [aesop safe] Chapter5.Real.nonzero_of_pos
attribute [aesop safe] Chapter5.Real.not_gt_and_eq
attribute [aesop safe] Chapter5.Real.not_gt_and_lt
attribute [aesop safe] Chapter5.Real.not_lt_and_eq
attribute [aesop safe] Chapter5.Real.not_pos_neg
attribute [aesop safe] Chapter5.Real.not_zero_neg
attribute [aesop safe] Chapter5.Real.not_zero_pos
attribute [aesop safe] Chapter5.Real.pos_add
attribute [aesop safe] Chapter5.Real.pos_mul
attribute [simp] Chapter5.Real.pos_of_coe
attribute [aesop unsafe 20%] Chapter5.Real.trichotomous
attribute [aesop unsafe 20%] Chapter5.Real.trichotomous'
attribute [simp] Chapter5.boundedAwayNeg_def
attribute [simp] Chapter5.boundedAwayPos_def
attribute [aesop safe] Chapter5.not_boundedAwayPos_boundedAwayNeg

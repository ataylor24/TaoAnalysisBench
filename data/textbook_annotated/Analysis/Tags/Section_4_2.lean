import Analysis.Section_4_2

attribute [simp] Section_4_2.PreRat.eq
attribute [simp] Section_4_2.Rat.add_eq
attribute [aesop safe] Section_4_2.Rat.add_lt_add_right
attribute [simp] Section_4_2.Rat.coe_Int_eq
attribute [simp] Section_4_2.Rat.coe_Nat_eq
attribute [simp] Section_4_2.Rat.coe_Rat_eq
attribute [simp] Section_4_2.Rat.div_eq
attribute [simp] Section_4_2.Rat.eq
attribute [aesop unsafe 30%] Section_4_2.Rat.ge_iff
attribute [aesop unsafe 50%] Section_4_2.Rat.gt_iff
attribute [simp] Section_4_2.Rat.intCast_add
attribute [simp] Section_4_2.Rat.intCast_mul
attribute [simp] Section_4_2.Rat.intCast_neg
attribute [simp] Section_4_2.Rat.inv_eq
attribute [simp] Section_4_2.Rat.inv_zero
attribute [simp] Section_4_2.Rat.le_iff
attribute [simp] Section_4_2.Rat.lt_iff
attribute [aesop unsafe 50%] Section_4_2.Rat.lt_trans
attribute [grind →] Section_4_2.Rat.lt_trans
attribute [simp] Section_4_2.Rat.mul_eq
attribute [aesop safe] Section_4_2.Rat.mul_lt_mul_right
attribute [grind →] Section_4_2.Rat.mul_lt_mul_right
attribute [aesop safe] Section_4_2.Rat.mul_lt_mul_right_of_neg
attribute [grind →] Section_4_2.Rat.mul_lt_mul_right_of_neg
attribute [simp] Section_4_2.Rat.natCast_succ
attribute [simp] Section_4_2.Rat.neg_eq
attribute [aesop safe] Section_4_2.Rat.not_gt_and_eq
attribute [aesop safe] Section_4_2.Rat.not_gt_and_lt
attribute [aesop safe] Section_4_2.Rat.not_lt_and_eq
attribute [aesop safe] Section_4_2.Rat.not_pos_and_neg
attribute [aesop safe] Section_4_2.Rat.not_zero_and_neg
attribute [aesop safe] Section_4_2.Rat.not_zero_and_pos
attribute [simp] Section_4_2.Rat.of_Nat_eq
attribute [simp] Section_4_2.Rat.sub_eq
attribute [aesop unsafe 20%] Section_4_2.Rat.trichotomous
attribute [aesop unsafe 20%] Section_4_2.Rat.trichotomous'

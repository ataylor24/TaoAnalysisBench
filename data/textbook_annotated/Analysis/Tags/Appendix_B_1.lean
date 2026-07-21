import Analysis.Appendix_B_1

attribute [aesop unsafe 20%] AppendixB.Digit.eq
attribute [simp] AppendixB.Digit.inj
attribute [aesop safe] AppendixB.Digit.lt
attribute [simp] AppendixB.Digit.mk_eq_iff
attribute [simp] AppendixB.Digit.toNat_mk
attribute [aesop unsafe 10%] AppendixB.IntDecimal.Int_bij
attribute [simp] AppendixB.PosintDecimal.append_toNat
attribute [simp] AppendixB.PosintDecimal.carry_succ
attribute [simp] AppendixB.PosintDecimal.carry_zero
attribute [simp] AppendixB.PosintDecimal.coe_inj
attribute [aesop safe] AppendixB.PosintDecimal.congr
attribute [aesop safe] AppendixB.PosintDecimal.congr'
attribute [simp] AppendixB.PosintDecimal.digit_eq
attribute [aesop unsafe 50%] AppendixB.PosintDecimal.eq_append
attribute [aesop unsafe 10%] AppendixB.PosintDecimal.exists_unique
attribute [aesop safe] AppendixB.PosintDecimal.head_ne_zero
attribute [aesop safe] AppendixB.PosintDecimal.head_ne_zero'
attribute [aesop safe] AppendixB.PosintDecimal.leading_nonzero
attribute [aesop safe] AppendixB.PosintDecimal.length_pos
attribute [simp] AppendixB.PosintDecimal.out_of_range_eq_zero
attribute [aesop safe] AppendixB.PosintDecimal.pos
attribute [aesop safe] AppendixB.PosintDecimal.sum_digit_lt
attribute [aesop unsafe 20%] AppendixB.PosintDecimal.sum_eq
attribute [simp] AppendixB.PosintDecimal.ten_eq_ten

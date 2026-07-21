import Analysis.Section_8_1

attribute [aesop unsafe 50%] Chapter8.AtMostCountable.equiv
attribute [simp] Chapter8.AtMostCountable.iff
attribute [aesop unsafe 50%] Chapter8.AtMostCountable.image
attribute [aesop safe] Chapter8.AtMostCountable.image_nat
attribute [aesop unsafe 50%] Chapter8.AtMostCountable.subset
attribute [aesop unsafe 50%] Chapter8.AtMostCountable.subset'
attribute [grind →] Chapter8.AtMostCountable.subset'
attribute [aesop unsafe 50%] Chapter8.CountablyInfinite.equiv
attribute [aesop unsafe 50%] Chapter8.CountablyInfinite.iff
attribute [simp] Chapter8.CountablyInfinite.iff'
attribute [aesop unsafe 30%] Chapter8.CountablyInfinite.iff_image_inj
attribute [aesop safe] Chapter8.CountablyInfinite.lower_diag
attribute [aesop unsafe 50%] Chapter8.CountablyInfinite.prod
attribute [aesop safe] Chapter8.CountablyInfinite.prod_nat
attribute [aesop unsafe 70%] Chapter8.CountablyInfinite.toCountable
attribute [aesop unsafe 70%] Chapter8.CountablyInfinite.toInfinite
attribute [aesop unsafe 50%] Chapter8.CountablyInfinite.union
attribute [simp] Chapter8.EqualCard.iff
attribute [aesop unsafe 30%] Chapter8.EqualCard.iff'
attribute [aesop safe] Chapter8.EqualCard.refl
attribute [aesop unsafe 60%] Chapter8.EqualCard.symm
attribute [aesop unsafe 30%] Chapter8.EqualCard.trans
attribute [aesop safe] Chapter8.EqualCard.univ
attribute [aesop unsafe 50%] Chapter8.Finite.equiv
attribute [aesop safe] Chapter8.Int.countablyInfinite
attribute [aesop safe] Chapter8.Nat.atMostCountable_subset
attribute [aesop safe] Chapter8.Nat.countable_of_infinite
attribute [aesop safe] Chapter8.Nat.exists_unique_min
attribute [simp] Chapter8.Nat.min_empty
attribute [aesop unsafe 50%] Chapter8.Nat.min_eq
attribute [grind →] Chapter8.Nat.min_eq
attribute [aesop unsafe 50%] Chapter8.Nat.min_eq_find
attribute [aesop unsafe 50%] Chapter8.Nat.min_eq_sInf
attribute [grind →] Chapter8.Nat.min_eq_sInf
attribute [aesop safe] Chapter8.Nat.min_spec
attribute [grind →] Chapter8.Nat.min_spec
attribute [aesop unsafe 10%] Chapter8.Nat.monotone_enum_of_infinite
attribute [aesop safe] Chapter8.Rat.countablyInfinite
attribute [aesop safe] Chapter8.explicit_bijection_spec

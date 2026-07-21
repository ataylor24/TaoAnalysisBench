import Analysis.Section_9_4

attribute [aesop safe] Chapter9.Continuous.abs
attribute [aesop safe] Chapter9.Continuous.exp
attribute [grind →] Chapter9.Continuous.exp
attribute [aesop safe] Chapter9.Continuous.exp'
attribute [aesop safe] Chapter9.Continuous.polynomial
attribute [aesop unsafe 50%] Chapter9.ContinuousOn.restrict
attribute [grind →] Chapter9.ContinuousOn.restrict
attribute [aesop safe] Chapter9.ContinuousWithinAt.add
attribute [grind →] Chapter9.ContinuousWithinAt.add
attribute [aesop unsafe 50%] Chapter9.ContinuousWithinAt.comp
attribute [grind →] Chapter9.ContinuousWithinAt.comp
attribute [aesop unsafe 50%] Chapter9.ContinuousWithinAt.div'
attribute [grind →] Chapter9.ContinuousWithinAt.div'
attribute [simp] Chapter9.ContinuousWithinAt.iff
attribute [aesop safe] Chapter9.ContinuousWithinAt.max
attribute [grind →] Chapter9.ContinuousWithinAt.max
attribute [aesop safe] Chapter9.ContinuousWithinAt.min
attribute [grind →] Chapter9.ContinuousWithinAt.min
attribute [aesop safe] Chapter9.ContinuousWithinAt.mul'
attribute [grind →] Chapter9.ContinuousWithinAt.mul'
attribute [aesop safe] Chapter9.ContinuousWithinAt.sub
attribute [grind →] Chapter9.ContinuousWithinAt.sub
attribute [aesop unsafe 50%] Filter.Tendsto.comp_of_continuous
attribute [grind →] Filter.Tendsto.comp_of_continuous

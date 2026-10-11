import Std
import Std.Internal.Rat

set_option autoImplicit false

/-
Pf8 Ghana audit reference specifications, pinned to Lean 4.19.0.

These theorems concern the definitions below. They do not assert that the
entire Python pipeline refines these definitions, that source data are correct,
or that demographic and selection models fit the biological observations.
No admitted proofs, custom axioms, or native_decide are used.
-/

namespace Pf8Audit

open Std.Internal

-- The biallelic majority rule after negative AD values have been clamped to 0.
-- false = reference; true = alternate; none = missing.
def resolveMajority (referenceDepth alternateDepth : Nat) : Option Bool :=
  if referenceDepth > alternateDepth then some false
  else if alternateDepth > referenceDepth then some true
  else none

theorem tie_is_missing (d : Nat) : resolveMajority d d = none := by
  simp [resolveMajority]

theorem reference_majority_is_reference (r a : Nat) (h : a < r) :
    resolveMajority r a = some false := by
  simp [resolveMajority, h]

theorem alternate_majority_is_alternate (r a : Nat) (h : r < a) :
    resolveMajority r a = some true := by
  have hn : ¬ a < r := by omega
  simp [resolveMajority, h, hn]

def referenceCount : List (Option Bool) → Nat
  | [] => 0
  | none :: xs => referenceCount xs
  | some false :: xs => referenceCount xs + 1
  | some true :: xs => referenceCount xs

def alternateCount : List (Option Bool) → Nat
  | [] => 0
  | none :: xs => alternateCount xs
  | some false :: xs => alternateCount xs
  | some true :: xs => alternateCount xs + 1

def calledCount : List (Option Bool) → Nat
  | [] => 0
  | none :: xs => calledCount xs
  | some _ :: xs => calledCount xs + 1

theorem one_allele_per_called_isolate (xs : List (Option Bool)) :
    referenceCount xs + alternateCount xs = calledCount xs := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    cases x with
    | none => simpa [referenceCount, alternateCount, calledCount] using ih
    | some b =>
      cases b <;> simp_all [referenceCount, alternateCount, calledCount] <;> omega

theorem called_count_is_bounded_by_samples (xs : List (Option Bool)) :
    calledCount xs ≤ xs.length := by
  induction xs with
  | nil => simp [calledCount]
  | cons x xs ih =>
    cases x <;> simp_all [calledCount] <;> omega

def countWhere {α : Type} (p : α → Bool) : List α → Nat
  | [] => 0
  | x :: xs => (if p x then 1 else 0) + countWhere p xs

theorem conjunction_cannot_exceed_component {α : Type}
    (p q : α → Bool) (xs : List α) :
    countWhere (fun x => p x && q x) xs ≤ countWhere p xs := by
  induction xs with
  | nil => simp [countWhere]
  | cons x xs ih =>
    cases hp : p x <;> cases hq : q x <;> simp_all [countWhere] <;> omega

-- Same marginal frequencies, different joint frequencies: linkage/co-occurrence
-- cannot be established by matching marginal frequencies alone.
def together : List (Bool × Bool) :=
  [(true, true), (true, true), (false, false), (false, false)]
def apart : List (Bool × Bool) :=
  [(true, false), (true, false), (false, true), (false, true)]

theorem same_marginals_do_not_identify_haplotype :
    countWhere Prod.fst together = countWhere Prod.fst apart ∧
    countWhere Prod.snd together = countWhere Prod.snd apart ∧
    countWhere (fun x => x.1 && x.2) together ≠
      countWhere (fun x => x.1 && x.2) apart := by decide

-- Cross-multiplied frequency thresholds avoid floating-point rounding.
def passesMaf05 (minor called : Nat) : Prop :=
  0 < called ∧ 2 * minor ≤ called ∧ called ≤ 20 * minor

-- At most 25 alleles are available in the transitional-zone sample.
-- A retained genome-wide site has at least 90% of 1900 calls = 1710 calls.
theorem transitional_private_variant_cannot_pass
    (minor called : Nat) (hm : minor ≤ 25) (hn : 1710 ≤ called) :
    ¬ passesMaf05 minor called := by
  unfold passesMaf05
  omega

-- 82/204 is about 40.2% within the coastal sample, but it remains below 5%
-- pooled even at the minimum retained-site called denominator.
theorem coast_private_about_40_percent_cannot_pass
    (called : Nat) (hn : 1710 ≤ called) : ¬ passesMaf05 82 called := by
  unfold passesMaf05
  omega

def passesMissing10 (missing total : Nat) : Prop :=
  0 < total ∧ 10 * missing ≤ total

-- Removing a called sample can raise variant missingness; the rate must be
-- recomputed on the retained sample set, rather than presumed to decrease.
theorem sample_removal_can_raise_variant_missingness :
    passesMissing10 1 10 ∧ ¬ passesMissing10 1 9 := by
  unfold passesMissing10
  decide

theorem shape_does_not_prove_identifier_alignment :
    (["a", "b"] : List String).length = (["b", "a"] : List String).length ∧
    (["a", "b"] : List String) ≠ ["b", "a"] := by decide

-- Sum of locus numerators divided by sum of denominators differs from the
-- unweighted average of locus ratios. Here ratios are 1/2 and 0/1.
theorem ratio_of_sums_is_not_mean_of_ratios :
    ((1 : Rat) + 0) / (2 + 1) ≠ ((1 : Rat) / 2 + 0 / 1) / 2 := by decide

-- This algebraic expression represents the estimator only on its valid domain:
-- n,m >= 2, p,q in [0,1], and a positive denominator. Nat subtraction and Rat
-- division are total in Lean; their values outside that domain are not estimates.
def hudsonTwoPop (p q : Rat) (n m : Nat) : Rat :=
  ((p - q) * (p - q) - p * (1 - p) / mkRat (Int.ofNat (n - 1)) 1
    - q * (1 - q) / mkRat (Int.ofNat (m - 1)) 1) /
      (p * (1 - q) + q * (1 - p))

-- Counting two copies of a haploid allele changes the finite-sample correction,
-- even though the allele frequencies themselves do not change.
theorem doubled_counts_change_hudson_correction :
    hudsonTwoPop 0 (1 / 2) 2 2 = 0 ∧
    hudsonTwoPop 0 (1 / 2) 4 4 = 1 / 3 := by decide

-- A simulated-tail p-value has a nonzero numerator and a numerator no larger
-- than its denominator. Calibration of the fitted null is a separate question.
theorem simulated_tail_ratio_bounds (tail n : Nat) (h : tail ≤ n) :
    0 < tail + 1 ∧ tail + 1 ≤ n + 1 := by omega

theorem expected_false_positive_ratio_arithmetic :
    ((3916 : Rat) / 1000) / 19 = (979 : Rat) / 4750 := by decide

-- A zero observed count alone cannot exclude unobserved positive prevalence.
-- Without a probability model, an observation of 0 is compatible with the
-- presence of a positive count in an unsampled group.
theorem sampled_zero_does_not_force_population_zero :
    ∃ sampled unsampled : Nat, sampled = 0 ∧ sampled + unsampled > 0 := by
  exact ⟨0, 1, rfl, by decide⟩

#print axioms tie_is_missing
#print axioms reference_majority_is_reference
#print axioms alternate_majority_is_alternate
#print axioms one_allele_per_called_isolate
#print axioms called_count_is_bounded_by_samples
#print axioms conjunction_cannot_exceed_component
#print axioms same_marginals_do_not_identify_haplotype
#print axioms transitional_private_variant_cannot_pass
#print axioms coast_private_about_40_percent_cannot_pass
#print axioms sample_removal_can_raise_variant_missingness
#print axioms shape_does_not_prove_identifier_alignment
#print axioms ratio_of_sums_is_not_mean_of_ratios
#print axioms doubled_counts_change_hudson_correction
#print axioms simulated_tail_ratio_bounds
#print axioms expected_false_positive_ratio_arithmetic
#print axioms sampled_zero_does_not_force_population_zero

end Pf8Audit

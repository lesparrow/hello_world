# Valeurs de référence des calculs de puissance, calculées par R avec le paquet pwr
# (Champely, formules de Cohen 1988) et, pour le test t, par power.t.test(strict = TRUE) de R de base.
# Usage : Rscript tests/reference/r_power.R tests/reference/r_power.csv
# Taille d'échantillon : plus petit entier n tel que la puissance calculée par pwr atteigne la cible
# (recherche sur les entiers, sans la tolérance de uniroot). Plus petit effet détectable : uniroot avec
# une tolérance de 1e-13 sur la fonction de puissance de pwr.

suppressPackageStartupMessages(library(pwr))
args <- commandArgs(trailingOnly = TRUE)
out_file <- if (length(args) >= 1) args[1] else "tests/reference/r_power.csv"
rows <- list()
put <- function(case, key, value) {
  rows[[length(rows) + 1]] <<- data.frame(case = case, key = key, value = sprintf("%.17g", as.numeric(value)))
}
alt <- function(sides) if (sides == "two") "two.sided" else "greater"

first_n <- function(f, target, lo) { n <- lo; while (f(n) < target) n <- n + 1; n }
solve_eff <- function(f, target, upper) uniroot(function(e) f(e) - target, c(1e-12, upper), tol = 1e-13)$root

# Test t, deux groupes : n2 = ceiling(ratio * n1)
t2_ss <- function(case, d, sig, pw, sides = "two", ratio = 1) {
  f <- function(n) pwr.t2n.test(n1 = n, n2 = max(2, ceiling(ratio * n - 1e-9)), d = d, sig.level = sig,
                                alternative = alt(sides))$power
  n1 <- first_n(f, pw, 2); n2 <- max(2, ceiling(ratio * n1 - 1e-9))
  put(case, "n1", n1); put(case, "n2", n2); put(case, "power", f(n1))
  if (ratio == 1) put(case, "power_base", power.t.test(n = n1, delta = d, sd = 1, sig.level = sig,
                                                        alternative = if (sides == "two") "two.sided" else "one.sided",
                                                        strict = TRUE)$power)
}
t2_pw <- function(case, d, n1, n2, sig, sides = "two")
  put(case, "power", pwr.t2n.test(n1 = n1, n2 = n2, d = d, sig.level = sig, alternative = alt(sides))$power)
t2_eff <- function(case, n1, n2, sig, pw, sides = "two")
  put(case, "effect", solve_eff(function(e) pwr.t2n.test(n1 = n1, n2 = n2, d = e, sig.level = sig,
                                                         alternative = alt(sides))$power, pw, 50))

t1_ss <- function(case, type, d, sig, pw, sides = "two") {
  f <- function(n) pwr.t.test(n = n, d = d, sig.level = sig, type = type, alternative = alt(sides))$power
  n <- first_n(f, pw, 2)
  put(case, "n1", n); put(case, "power", f(n))
  put(case, "power_base", power.t.test(n = n, delta = d, sd = 1, sig.level = sig, type = type,
                                       alternative = if (sides == "two") "two.sided" else "one.sided",
                                       strict = TRUE)$power)
}
t1_pw <- function(case, type, d, n, sig, sides = "two")
  put(case, "power", pwr.t.test(n = n, d = d, sig.level = sig, type = type, alternative = alt(sides))$power)
t1_eff <- function(case, type, n, sig, pw, sides = "two")
  put(case, "effect", solve_eff(function(e) pwr.t.test(n = n, d = e, sig.level = sig, type = type,
                                                       alternative = alt(sides))$power, pw, 50))

p2_ss <- function(case, p1, p2, sig, pw, sides = "two", ratio = 1) {
  h <- abs(ES.h(p1, p2))
  f <- function(n) pwr.2p2n.test(h = h, n1 = n, n2 = max(2, ceiling(ratio * n - 1e-9)), sig.level = sig,
                                 alternative = alt(sides))$power
  n1 <- first_n(f, pw, 2)
  put(case, "h", h); put(case, "n1", n1); put(case, "n2", max(2, ceiling(ratio * n1 - 1e-9))); put(case, "power", f(n1))
}
p2_pw <- function(case, p1, p2, n1, n2, sig, sides = "two")
  put(case, "power", pwr.2p2n.test(h = abs(ES.h(p1, p2)), n1 = n1, n2 = n2, sig.level = sig,
                                   alternative = alt(sides))$power)
p2_eff <- function(case, n1, n2, sig, pw, sides = "two")
  put(case, "effect", solve_eff(function(e) pwr.2p2n.test(h = e, n1 = n1, n2 = n2, sig.level = sig,
                                                          alternative = alt(sides))$power, pw, pi))

c_ss <- function(case, w, df, sig, pw) {
  f <- function(n) pwr.chisq.test(w = w, N = n, df = df, sig.level = sig)$power
  n <- first_n(f, pw, 2)
  put(case, "n1", n); put(case, "power", f(n))
}
c_pw <- function(case, w, n, df, sig) put(case, "power", pwr.chisq.test(w = w, N = n, df = df, sig.level = sig)$power)
c_eff <- function(case, n, df, sig, pw)
  put(case, "effect", solve_eff(function(e) pwr.chisq.test(w = e, N = n, df = df, sig.level = sig)$power, pw, 50))

r_ss <- function(case, r, sig, pw, sides = "two") {
  f <- function(n) pwr.r.test(n = n, r = r, sig.level = sig, alternative = alt(sides))$power
  n <- first_n(f, pw, 4)
  put(case, "n1", n); put(case, "power", f(n))
}
r_pw <- function(case, r, n, sig, sides = "two")
  put(case, "power", pwr.r.test(n = n, r = r, sig.level = sig, alternative = alt(sides))$power)
r_eff <- function(case, n, sig, pw, sides = "two")
  put(case, "effect", solve_eff(function(e) pwr.r.test(n = n, r = e, sig.level = sig,
                                                       alternative = alt(sides))$power, pw, 1 - 1e-12))

t2_ss("t2_ss_d05", 0.5, 0.05, 0.80)
t2_ss("t2_ss_d02_one_90", 0.2, 0.05, 0.90, "one")
t2_ss("t2_ss_d08_a01", 0.8, 0.01, 0.95)
t2_ss("t2_ss_ratio2", 0.5, 0.05, 0.80, "two", 2)
t2_ss("t2_ss_ratio05_one", 0.4, 0.05, 0.85, "one", 0.5)
t2_pw("t2_pw_unequal", 0.6, 30, 45, 0.05)
t2_pw("t2_pw_small_one", 0.3, 12, 9, 0.10, "one")
t2_eff("t2_eff_40", 40, 40, 0.05, 0.80)
t2_eff("t2_eff_25_60_one", 25, 60, 0.05, 0.90, "one")

t1_ss("paired_ss_d03", "paired", 0.3, 0.05, 0.80)
t1_ss("paired_ss_d06_one", "paired", 0.6, 0.05, 0.90, "one")
t1_pw("paired_pw_n25", "paired", 0.5, 25, 0.05)
t1_eff("paired_eff_n18", "paired", 18, 0.05, 0.80)
t1_ss("one_ss_d04_a01", "one.sample", 0.4, 0.01, 0.80)
t1_pw("one_pw_n10_one", "one.sample", 0.7, 10, 0.05, "one")
t1_eff("one_eff_n60", "one.sample", 60, 0.05, 0.95)

p2_ss("prop_ss_40_60", 0.4, 0.6, 0.05, 0.80)
p2_ss("prop_ss_10_20_one", 0.10, 0.20, 0.05, 0.90, "one")
p2_ss("prop_ss_ratio3", 0.30, 0.50, 0.05, 0.80, "two", 3)
p2_pw("prop_pw_unequal", 0.30, 0.50, 60, 80, 0.05)
p2_eff("prop_eff_100", 50, 50, 0.05, 0.80)

c_ss("chi2_ss_w03_df2", 0.3, 2, 0.05, 0.80)
c_ss("chi2_ss_w01_df1", 0.1, 1, 0.05, 0.90)
c_pw("chi2_pw_w02_df4", 0.2, 200, 4, 0.05)
c_eff("chi2_eff_n150_df1", 150, 1, 0.05, 0.80)

r_ss("r_ss_03", 0.3, 0.05, 0.80)
r_ss("r_ss_02_one", 0.2, 0.05, 0.90, "one")
r_ss("r_ss_05_a01", 0.5, 0.01, 0.80)
r_pw("r_pw_n50", 0.4, 50, 0.05)
r_pw("r_pw_n30_one", 0.25, 30, 0.05, "one")
r_eff("r_eff_n80", 80, 0.05, 0.80)

out <- do.call(rbind, rows)
write.csv(out, out_file, row.names = FALSE, quote = FALSE)
cat(sprintf("%d valeurs de référence (puissance) écrites dans %s (%s, pwr %s)\n", nrow(out), out_file,
            R.version.string, as.character(packageVersion("pwr"))))

# Valeurs de référence calculées par R (fonctions de base uniquement, sans paquet).
# Usage : Rscript tests/reference/r_reference.R tests/reference/data tests/reference/r_results.csv
# Chaque ligne du fichier produit : cas, clé, valeur (17 chiffres significatifs).

args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args) >= 1) args[1] else "tests/reference/data"
out_file <- if (length(args) >= 2) args[2] else "tests/reference/r_results.csv"

rd <- function(name) read.csv(file.path(data_dir, name), stringsAsFactors = FALSE, na.strings = c("", "NA"))
rows <- list()
put <- function(case, key, value) {
  rows[[length(rows) + 1]] <<- data.frame(case = case, key = key, value = sprintf("%.17g", as.numeric(value)))
}

g1 <- function(x) { n <- length(x); m <- mean(x); m2 <- mean((x - m)^2); m3 <- mean((x - m)^3)
  (m3 / m2^1.5) * sqrt(n * (n - 1)) / (n - 2) }
g2 <- function(x) { n <- length(x); m <- mean(x); m2 <- mean((x - m)^2); m4 <- mean((x - m)^4)
  ((n + 1) * (m4 / m2^2 - 3) + 6) * (n - 1) / ((n - 2) * (n - 3)) }
hedges_j <- function(df) exp(lgamma(df / 2) - log(sqrt(df / 2)) - lgamma((df - 1) / 2))

describe <- function(case, x, conf = 0.95) {
  x <- x[!is.na(x)]
  tt <- t.test(x, conf.level = conf)
  q <- quantile(x, c(0.25, 0.5, 0.75), type = 7)
  sw <- shapiro.test(x)
  put(case, "n", length(x)); put(case, "mean", mean(x)); put(case, "sd", sd(x))
  put(case, "se", sd(x) / sqrt(length(x))); put(case, "ci_low", tt$conf.int[1]); put(case, "ci_high", tt$conf.int[2])
  put(case, "q1", q[1]); put(case, "median", q[2]); put(case, "q3", q[3])
  put(case, "min", min(x)); put(case, "max", max(x))
  put(case, "skewness", g1(x)); put(case, "kurtosis", g2(x))
  put(case, "shapiro_w", sw$statistic); put(case, "shapiro_p", sw$p.value)
}

two_t <- function(case, d, y, g, levels, var.equal, alternative = "two.sided", conf = 0.95) {
  d <- d[!is.na(d[[y]]) & d[[g]] %in% levels, ]
  a <- d[[y]][d[[g]] == levels[1]]; b <- d[[y]][d[[g]] == levels[2]]
  tt <- t.test(a, b, var.equal = var.equal, alternative = alternative, conf.level = conf)
  put(case, "t", tt$statistic); put(case, "df", tt$parameter); put(case, "p", tt$p.value)
  put(case, "mean_diff", mean(a) - mean(b))
  put(case, "ci_low", tt$conf.int[1]); put(case, "ci_high", tt$conf.int[2])
  na <- length(a); nb <- length(b)
  sp <- sqrt(((na - 1) * var(a) + (nb - 1) * var(b)) / (na + nb - 2))
  s_eff <- if (var.equal) sp else sqrt((var(a) + var(b)) / 2)
  d_ <- (mean(a) - mean(b)) / s_eff
  put(case, "cohen_d", d_); put(case, "hedges_g", d_ * hedges_j(na + nb - 2))
  # Levene (Brown-Forsythe) : ANOVA sur les écarts absolus à la médiane
  dev <- c(abs(a - median(a)), abs(b - median(b))); grp <- factor(rep(1:2, c(na, nb)))
  an <- anova(lm(dev ~ grp))
  put(case, "levene_f", an[["F value"]][1]); put(case, "levene_p", an[["Pr(>F)"]][1])
}

mw <- function(case, d, y, g, levels, alternative = "two.sided") {
  d <- d[!is.na(d[[y]]) & d[[g]] %in% levels, ]
  a <- d[[y]][d[[g]] == levels[1]]; b <- d[[y]][d[[g]] == levels[2]]
  w <- suppressWarnings(wilcox.test(a, b, alternative = alternative))
  put(case, "w", w$statistic); put(case, "p", w$p.value)
  put(case, "rank_biserial", 2 * w$statistic / (length(a) * length(b)) - 1)
}

paired <- function(case, x, y, alternative = "two.sided", conf = 0.95) {
  ok <- !is.na(x) & !is.na(y); x <- x[ok]; y <- y[ok]
  tt <- t.test(x, y, paired = TRUE, alternative = alternative, conf.level = conf)
  put(case, "t", tt$statistic); put(case, "df", tt$parameter); put(case, "p", tt$p.value)
  put(case, "mean_diff", mean(x - y)); put(case, "ci_low", tt$conf.int[1]); put(case, "ci_high", tt$conf.int[2])
  put(case, "cohen_dz", mean(x - y) / sd(x - y))
}

wil <- function(case, x, y, alternative = "two.sided") {
  w <- suppressWarnings(wilcox.test(x, y, paired = TRUE, alternative = alternative))
  dd <- (x - y)[x != y]; r <- rank(abs(dd))
  put(case, "v", w$statistic); put(case, "p", w$p.value)
  put(case, "rank_biserial", (sum(r[dd > 0]) - sum(r[dd < 0])) / sum(r))
}

pear <- function(case, x, y, alternative = "two.sided", conf = 0.95) {
  ct <- cor.test(x, y, alternative = alternative, conf.level = conf)
  put(case, "r", ct$estimate); put(case, "t", ct$statistic); put(case, "df", ct$parameter)
  put(case, "p", ct$p.value); put(case, "ci_low", ct$conf.int[1]); put(case, "ci_high", ct$conf.int[2])
}

spear <- function(case, x, y, alternative = "two.sided") {
  ct <- suppressWarnings(cor.test(x, y, method = "spearman", alternative = alternative))
  put(case, "rho", ct$estimate); put(case, "s", ct$statistic); put(case, "p", ct$p.value)
}

chi <- function(case, a, b, correct = TRUE) {
  tab <- table(a, b)
  ct <- suppressWarnings(chisq.test(tab, correct = correct))
  plain <- suppressWarnings(chisq.test(tab, correct = FALSE))$statistic
  put(case, "chi2", ct$statistic); put(case, "df", ct$parameter); put(case, "p", ct$p.value)
  put(case, "cramer_v", sqrt(plain / (sum(tab) * (min(dim(tab)) - 1))))
  sr <- ct$stdres
  for (i in seq_len(nrow(sr))) for (j in seq_len(ncol(sr))) put(case, sprintf("stdres_%d_%d", i - 1, j - 1), sr[i, j])
  ex <- ct$expected
  for (i in seq_len(nrow(ex))) for (j in seq_len(ncol(ex))) put(case, sprintf("expected_%d_%d", i - 1, j - 1), ex[i, j])
}

fis <- function(case, a, b, alternative = "two.sided", conf = 0.95) {
  tab <- table(a, b)
  ft <- fisher.test(tab, alternative = alternative, conf.level = conf)
  put(case, "p", ft$p.value)
  if (all(dim(tab) == 2)) {
    put(case, "odds_ratio", ft$estimate); put(case, "ci_low", ft$conf.int[1]); put(case, "ci_high", ft$conf.int[2])
  }
}

gr <- rd("groups.csv"); gt <- rd("groups_ties.csv"); sm <- rd("small.csv")
pa <- rd("paired.csv"); pt <- rd("paired_ties.csv")
co <- rd("corr.csv"); cs <- rd("corr_small.csv"); cti <- rd("corr_ties.csv")
ca <- rd("cat.csv"); cas <- rd("cat_small.csv"); cr <- rd("cat_small_rxc.csv"); cm <- rd("cat_medium.csv")

describe("desc_groups_y", gr$y)
describe("desc_corr_x_99", co$x, conf = 0.99)
describe("desc_ties_score", gt$score)

two_t("welch_groups", gr, "y", "g", c("A", "B"), FALSE)
two_t("welch_groups_less_90", gr, "y", "g", c("A", "B"), FALSE, "less", 0.90)
two_t("student_groups", gr, "y", "g", c("A", "B"), TRUE)
two_t("student_groups_greater_99", gr, "y", "g", c("A", "B"), TRUE, "greater", 0.99)
two_t("welch_small", sm, "y", "g", c("C", "T"), FALSE)
two_t("student_small_reversed", sm, "y", "g", c("T", "C"), TRUE)
two_t("welch_ties", gt, "score", "g", c("F", "H"), FALSE)

mw("mw_groups", gr, "y", "g", c("A", "B"))
mw("mw_groups_greater", gr, "y", "g", c("A", "B"), "greater")
mw("mw_small", sm, "y", "g", c("C", "T"))
mw("mw_small_less", sm, "y", "g", c("C", "T"), "less")
mw("mw_ties", gt, "score", "g", c("F", "H"))
mw("mw_ties_less", gt, "score", "g", c("F", "H"), "less")

paired("paired_t", pa$apres, pa$avant)
paired("paired_t_less_99", pa$apres, pa$avant, "less", 0.99)
paired("paired_t_ties", pt$t2, pt$t1)
wil("wilcoxon", pa$apres, pa$avant)
wil("wilcoxon_greater", pa$apres, pa$avant, "greater")
wil("wilcoxon_ties", pt$t2, pt$t1)
wil("wilcoxon_ties_less", pt$t2, pt$t1, "less")

pear("pearson", co$x, co$y)
pear("pearson_greater_90", co$x, co$y, "greater", 0.90)
pear("pearson_small", cs$x, cs$y)
pear("pearson_ties", cti$x, cti$y)
spear("spearman", co$x, co$y)
spear("spearman_less", co$x, co$y, "less")
spear("spearman_greater", co$x, co$y, "greater")
spear("spearman_small", cs$x, cs$y)
spear("spearman_small_greater", cs$x, cs$y, "greater")
spear("spearman_ties", cti$x, cti$y)

chi("chi2_2x2_yates", ca$sexe, ca$fumeur)
chi("chi2_2x2_plain", ca$sexe, ca$fumeur, FALSE)
chi("chi2_2x3", ca$sexe, ca$satisfaction)
chi("chi2_3x3_small", cr$r, cr$c)

fis("fisher_2x2", cas$traitement, cas$guerison)
fis("fisher_2x2_less", cas$traitement, cas$guerison, "less")
fis("fisher_2x2_greater_90", cas$traitement, cas$guerison, "greater", 0.90)
fis("fisher_2x2_sexe", ca$sexe, ca$fumeur)
fis("fisher_rxc_small", cr$r, cr$c)
fis("fisher_2x3", ca$sexe, ca$satisfaction)
fis("fisher_3x3_medium", cm$r, cm$c)
chi("chi2_3x3_medium", cm$r, cm$c)

out <- do.call(rbind, rows)
write.csv(out, out_file, row.names = FALSE, quote = FALSE)
cat(sprintf("%d valeurs de référence écrites dans %s (%s)\n", nrow(out), out_file, R.version.string))

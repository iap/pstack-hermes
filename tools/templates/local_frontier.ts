export function localFrontier(repo: string): readonly FrontierPr[] {
  let currentBranch: string;
  try {
    currentBranch = execFileSync(
      "git",
      ["rev-parse", "--abbrev-ref", "HEAD"],
      { cwd: repo, encoding: "utf8", env: { ...process.env, NO_COLOR: "1" }, stdio: ["ignore", "pipe", "pipe"] }
    ).trim();
  } catch (error) {
    throw new UserError(`git rev-parse HEAD failed: ${errorMessage(error)}`);
  }

  let allBranches: string[];
  try {
    allBranches = execFileSync(
      "git",
      ["branch", "--format=%(refname:short)"],
      { cwd: repo, encoding: "utf8", env: { ...process.env, NO_COLOR: "1" }, stdio: ["ignore", "pipe", "pipe"] }
    )
      .split("\n")
      .map((b) => b.trim())
      .filter((b) => b.length > 0);
  } catch (error) {
    throw new UserError(`git branch listing failed: ${errorMessage(error)}`);
  }

  const stackBranches: string[] = [];
  for (const branch of allBranches) {
    if (branch === currentBranch) { stackBranches.push(branch); continue; }
    try {
      execFileSync("git", ["merge-base", "--is-ancestor", `refs/heads/${branch}`, "HEAD"], { cwd: repo, encoding: "utf8", env: { ...process.env, NO_COLOR: "1" }, stdio: ["ignore", "pipe", "pipe"] });
      stackBranches.push(branch);
    } catch {
      try {
        execFileSync("git", ["merge-base", "--is-ancestor", "HEAD", `refs/heads/${branch}`], { cwd: repo, encoding: "utf8", env: { ...process.env, NO_COLOR: "1" }, stdio: ["ignore", "pipe", "pipe"] });
        stackBranches.push(branch);
      } catch { /* unrelated */ }
    }
  }

  // Ancestry decides the order: ancestors first, then the current branch,
  // then descendants. Excluded (unrelated) branches never reach this sort.
  stackBranches.sort((a, b) => {
    try {
      execFileSync("git", ["merge-base", "--is-ancestor", `refs/heads/${a}`, `refs/heads/${b}`], { cwd: repo, encoding: "utf8", env: { ...process.env, NO_COLOR: "1" }, stdio: ["ignore", "pipe", "pipe"] });
      return -1; // a is ancestor of b
    } catch { /* a is not ancestor of b */ }
    try {
      execFileSync("git", ["merge-base", "--is-ancestor", `refs/heads/${b}`, `refs/heads/${a}`], { cwd: repo, encoding: "utf8", env: { ...process.env, NO_COLOR: "1" }, stdio: ["ignore", "pipe", "pipe"] });
      return 1; // b is ancestor of a
    } catch { /* neither is ancestor */ }
    return a.localeCompare(b);
  });

  const result: FrontierPr[] = [];
  for (const branch of stackBranches) {
    try {
      const sha = execFileSync("git", ["rev-parse", `refs/heads/${branch}`], { cwd: repo, encoding: "utf8", env: { ...process.env, NO_COLOR: "1" }, stdio: ["ignore", "pipe", "pipe"] }).trim();
      result.push({ pr: 0, branches: branch, sha, state: "OPEN" });
    } catch (error) { /* skip */ }
  }
  if (result.length === 0) {
    throw new UserError("local stack discovery found no branches in the current stack");
  }
  return result;
}

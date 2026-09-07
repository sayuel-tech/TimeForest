/** Mirrors the server's auto-export gate without predicting candidate validation. */
export function finishesReview(project, index, attempt) {
  const segments = project.segments || [];
  const selected = segments[index];
  if (!selected || (attempt && attempt !== selected.selected)) return false;
  return segments.every(
    (s, i) => i === index || ["accepted", "done"].includes(s.status),
  );
}

/** Follow lifecycle edges once, allowing users to revisit review during export. */
export function exportNavigation(project) {
  let previousStatus = project.status;
  let previousFile = project.export?.file || project.export?.url;
  return (next) => {
    const file = next.export?.file || next.export?.url;
    const navigate =
      (next.status === "assembling" && previousStatus !== "assembling") ||
      (next.status === "complete" &&
        (previousStatus !== "complete" || file !== previousFile));
    previousStatus = next.status;
    previousFile = file;
    return navigate;
  };
}

import { defineRailway, github, project, service } from "railway/iac";

export default defineRailway(() => {
  const web = service("web", {
    source: github("Teriyake4/Berkeley-AI-Hackathon"),
    build: "npm run build",
    start: "next start",
  });

  return project("Berkeley-AI-Hackathon", {
    resources: [web],
  });
});

// GoThea Frontend Application Logic (Milestone 1)

let currentProfile = null;
let currentSubjects = [];

// DOM Elements
const statusBadge = document.getElementById("status-badge");
const statusText = document.getElementById("status-text");
const badgeGrade = document.getElementById("badge-grade");
const userGreeting = document.getElementById("user-greeting");
const userSubtitle = document.getElementById("user-subtitle");
const statSubjectsCount = document.getElementById("stat-subjects-count");
const statTopicsCount = document.getElementById("stat-topics-count");
const dashboardSubjectsGrid = document.getElementById("dashboard-subjects-grid");
const subjectsDetailedList = document.getElementById("subjects-detailed-list");

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}


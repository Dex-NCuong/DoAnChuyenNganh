import { api } from "./api";

export async function fetchCalendarStatus() {
  const { data } = await api.get("/calendar/status");
  return data;
}

export async function getCalendarConnectUrl() {
  const { data } = await api.get("/calendar/connect");
  return data?.authorization_url;
}

export async function disconnectCalendar() {
  await api.post("/calendar/disconnect");
}

export async function createCalendarEvent(payload) {
  const { data } = await api.post("/calendar/events", payload);
  return data;
}

export async function listCalendarEvents(params = {}) {
  const { maxResults = 10, timeMin } = params;
  const query = { max_results: maxResults };
  if (timeMin) {
    query.time_min = timeMin;
  }
  const { data } = await api.get("/calendar/events", { params: query });
  return data;
}


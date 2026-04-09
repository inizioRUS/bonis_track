from __future__ import annotations

from typing import Any

import httpx

from core.config import settings


class AsanaToolError(Exception):
    pass


class AsanaTool:
    def __init__(self, asana_api_key) -> None:
        self.base_url = settings.asana_url.rstrip("/")
        self.timeout = settings.request_timeout_sec
        self.pat = asana_api_key

        headers = {
            "Content-Type": "application/json",
        }
        if self.pat:
            headers["Authorization"] = f"Bearer {self.pat}"

        self.headers = headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AsanaToolError(
                f"Asana request failed: {response.status_code} {response.text}"
            ) from exc

        data = response.json()
        return data if isinstance(data, dict) else {"data": data}

    async def get_me(self) -> dict[str, Any]:
        return await self._request("GET", "/users/me")

    async def get_workspaces(self) -> dict[str, Any]:
        return await self._request("GET", "/workspaces")

    async def get_projects(
        self,
        *,
        workspace_gid: str | None = None,
        team_gid: str | None = None,
        archived: bool | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}

        if workspace_gid:
            params["workspace"] = workspace_gid
        elif settings.default_asana_workspace_id:
            params["workspace"] = settings.default_asana_workspace_id

        if team_gid:
            params["team"] = team_gid
        elif settings.default_asana_team_id:
            params["team"] = settings.default_asana_team_id

        if archived is not None:
            params["archived"] = str(archived).lower()

        return await self._request("GET", "/projects", params=params)

    async def get_project(self, project_gid: str) -> dict[str, Any]:
        return await self._request("GET", f"/projects/{project_gid}")

    async def get_project_tasks(
        self,
        project_id: str | None = None,
        *,
        completed_since: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        pid = project_id or settings.default_asana_project_id
        if not pid:
            raise AsanaToolError("Asana project id is not configured")

        params: dict[str, Any] = {}
        if completed_since:
            params["completed_since"] = completed_since
        if limit:
            params["limit"] = limit

        return await self._request("GET", f"/projects/{pid}/tasks", params=params)

    async def get_task(
        self,
        task_gid: str,
        *,
        opt_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if opt_fields:
            params["opt_fields"] = ",".join(opt_fields)

        return await self._request("GET", f"/tasks/{task_gid}", params=params)

    async def search_tasks(
        self,
        text: str,
        *,
        workspace_gid: str | None = None,
        project_gid: str | None = None,
        completed: bool | None = None,
        assignee_gid: str | None = None,
        limit: int | None = 20,
    ) -> dict[str, Any]:
        workspace = workspace_gid or settings.default_asana_workspace_id
        if not workspace:
            raise AsanaToolError("Asana workspace id is not configured")

        params: dict[str, Any] = {
            "text": text,
        }

        if project_gid:
            params["projects.any"] = project_gid
        elif settings.default_asana_project_id:
            params["projects.any"] = settings.default_asana_project_id

        if completed is not None:
            params["completed"] = str(completed).lower()

        if assignee_gid:
            params["assignee.any"] = assignee_gid

        if limit:
            params["limit"] = limit

        return await self._request(
            "GET",
            f"/workspaces/{workspace}/tasks/search",
            params=params,
        )

    async def get_task_stories(self, task_gid: str) -> dict[str, Any]:
        return await self._request("GET", f"/tasks/{task_gid}/stories")

    async def add_comment_to_task(self, task_gid: str, text: str) -> dict[str, Any]:
        payload = {
            "data": {
                "text": text,
            }
        }
        return await self._request("POST", f"/tasks/{task_gid}/stories", json_body=payload)

    async def create_task(
        self,
        *,
        name: str,
        notes: str | None = None,
        project_gid: str | None = None,
        workspace_gid: str | None = None,
        assignee_gid: str | None = None,
        due_on: str | None = None,
        due_at: str | None = None,
        section_gid: str | None = None,
        tags: list[str] | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = project_gid or settings.default_asana_project_id
        workspace = workspace_gid or settings.default_asana_workspace_id
        assignee = assignee_gid or settings.default_asana_assignee_gid or None

        data: dict[str, Any] = {
            "name": name,
        }

        if notes:
            data["notes"] = notes
        if workspace:
            data["workspace"] = workspace
        if assignee:
            data["assignee"] = assignee
        if due_on:
            data["due_on"] = due_on
        if due_at:
            data["due_at"] = due_at
        if custom_fields:
            data["custom_fields"] = custom_fields

        if project:
            data["projects"] = [project]

        if tags:
            data["tags"] = tags

        created = await self._request("POST", "/tasks", json_body={"data": data})
        if section_gid:
            task_gid = created.get("data", {}).get("gid")
            if task_gid:
                await self.add_task_to_section(task_gid=task_gid, section_gid=section_gid)
        return created

    async def update_task(
        self,
        task_gid: str,
        *,
        name: str | None = None,
        notes: str | None = None,
        assignee_gid: str | None = None,
        completed: bool | None = None,
        due_on: str | None = None,
        due_at: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}

        if name is not None:
            data["name"] = name
        if notes is not None:
            data["notes"] = notes
        if assignee_gid is not None:
            data["assignee"] = assignee_gid
        if completed is not None:
            data["completed"] = completed
        if due_on is not None:
            data["due_on"] = due_on
        if due_at is not None:
            data["due_at"] = due_at
        if custom_fields is not None:
            data["custom_fields"] = custom_fields

        return await self._request("PUT", f"/tasks/{task_gid}", json_body={"data": data})

    async def create_section(
        self,
        *,
        project_gid: str | None = None,
        name: str,
    ) -> dict[str, Any]:
        project = project_gid or settings.default_asana_project_id
        if not project:
            raise AsanaToolError("Asana project id is not configured")

        payload = {
            "data": {
                "name": name,
            }
        }
        return await self._request("POST", f"/projects/{project}/sections", json_body=payload)

    async def get_sections(self, project_gid: str | None = None) -> dict[str, Any]:
        project = project_gid or settings.default_asana_project_id
        if not project:
            raise AsanaToolError("Asana project id is not configured")

        return await self._request("GET", f"/projects/{project}/sections")

    async def add_task_to_section(self, task_gid: str, section_gid: str) -> dict[str, Any]:
        payload = {
            "data": {
                "task": task_gid,
            }
        }
        return await self._request("POST", f"/sections/{section_gid}/addTask", json_body=payload)
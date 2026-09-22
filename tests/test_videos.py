def test_public_list_only_shows_ready_videos(client, make_video):
    ready = make_video(title="Ready")
    make_video(title="Pending", status="pending")
    make_video(title="Hidden", is_deleted=True)

    response = client.get("/videos")
    assert response.status_code == 200
    assert [v["id"] for v in response.json()] == [ready.id]
    assert response.json()[0]["url"] == f"/stream/{ready.id}"


def test_deleted_video_is_not_found(client, make_video):
    video = make_video(is_deleted=True)
    assert client.get(f"/videos/{video.id}").status_code == 404


def test_upload_stores_file_and_queues_job(client, fake_storage, fake_queue):
    response = client.post(
        "/videos/upload",
        data={"title": "  My clip ", "description": "desc"},
        files={"file": ("clip.mp4", b"\x00" * 16, "video/mp4")},
    )
    assert response.status_code == 202
    body = response.json()
    video_id = body["video"]["id"]
    assert body["video"]["title"] == "My clip"
    assert body["video"]["status"] == "pending"
    assert fake_storage["put"][0]["object_name"] == str(video_id)

    status = client.get(f"/uploads/{body['upload_id']}/status")
    assert status.json()["status"] == "pending"


def test_upload_rejects_non_video(client, fake_storage, fake_queue):
    response = client.post(
        "/videos/upload",
        data={"title": "Notes"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415
    assert fake_storage["put"] == []


def test_admin_list_includes_everything(client, auth_headers, make_video):
    make_video(status="pending")
    make_video(is_deleted=True)
    response = client.get("/admin/videos", headers=auth_headers)
    assert len(response.json()) == 2


def test_admin_can_edit_video(client, auth_headers, make_video):
    video = make_video()
    response = client.patch(
        f"/admin/videos/{video.id}", json={"title": "Renamed"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"


def test_soft_delete_keeps_files_and_can_be_restored(
    client, auth_headers, make_video, fake_storage, published_events
):
    video = make_video()

    assert client.delete(f"/admin/videos/{video.id}", headers=auth_headers).status_code == 204
    assert fake_storage["removed"] == []
    assert client.get(f"/videos/{video.id}").status_code == 404

    restored = client.post(f"/admin/videos/{video.id}/restore", headers=auth_headers)
    assert restored.json()["is_deleted"] is False
    assert client.get(f"/videos/{video.id}").status_code == 200
    assert published_events == [("deleted", video.id), ("restored", video.id)]


def test_edit_publishes_event(client, auth_headers, make_video, published_events):
    video = make_video()
    client.patch(f"/admin/videos/{video.id}", json={"title": "New"}, headers=auth_headers)
    assert published_events == [("updated", video.id)]


def test_permanent_delete_leaves_nothing_behind(
    client, auth_headers, fake_storage, fake_queue, published_events
):
    upload = client.post(
        "/videos/upload",
        data={"title": "Gone soon"},
        files={"file": ("clip.mp4", b"\x00" * 16, "video/mp4")},
    ).json()
    video_id = upload["video"]["id"]

    response = client.delete(f"/admin/videos/{video_id}?permanent=true", headers=auth_headers)
    assert response.status_code == 204
    assert fake_storage["removed"] == [video_id]
    assert fake_queue == {}
    assert client.get("/admin/videos", headers=auth_headers).json() == []
    assert client.get(f"/uploads/{upload['upload_id']}/status").status_code == 404
    assert published_events[-1] == ("removed", video_id)

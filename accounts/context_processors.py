def notifications(request):
    if not request.user.is_authenticated:
        return {}
    return {"unread_notification_count": request.user.notifications.filter(is_read=False).count()}

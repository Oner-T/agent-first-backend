import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ChatSession, Message
from .tasks import test_background_worker

@csrf_exempt # Disabling CSRF for local testing
def orchestrate_agent(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        prompt = data.get('prompt')
        session_id = data.get('session_id') # Might be null if it's a new chat

        # 1. Thread Management (Long-term Memory)
        if session_id:
            session = ChatSession.objects.get(id=session_id)
        else:
            # Create a new session and use the first few words as the title
            session = ChatSession.objects.create(title=prompt[:50])

        # 2. Save the User's Message to PostgreSQL
        Message.objects.create(
            session=session,
            role='user',
            content=prompt
        )

        # 3. Dispatch the heavy lifting to the Celery Worker
        # The .delay() method is what sends it to Redis instead of running it here
        test_background_worker.delay(str(session.id), prompt)

        # 4. Instantly return a 202 Accepted to the React Frontend
        return JsonResponse({
            'status': 'processing',
            'session_id': str(session.id),
            'message': 'Handed off to the Theorist Agent'
        }, status=202)
    
def get_session_history(request, session_id):
    if request.method == 'GET':
        try:
            session = ChatSession.objects.get(id=session_id)
            messages = session.messages.all().order_by('created_at')
            
            history = []
            for msg in messages:
                history.append({
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat()
                })
                
            return JsonResponse({
                "session_id": str(session.id),
                "title": session.title,
                "messages": history
            })
            
        except ObjectDoesNotExist:
            return JsonResponse({"error": "Session not found"}, status=404)
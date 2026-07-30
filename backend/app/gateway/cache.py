import hashlib
import json

import redis


class SearchCache:

    def __init__(self):

        self.redis = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True,
        )

        self.ttl = 60 * 15   # 15 minutes

    def build_key(self, request):

        payload = {
            "platform": request.platform,
            "job_title": request.job_title,
            "location": request.location,
            "experience": request.experience,
            "easy_apply": request.easy_apply,
            "work_mode": request.work_mode,
            "posted_within": request.posted_within,
        }

        raw = json.dumps(payload, sort_keys=True)

        return "jobs:" + hashlib.sha256(raw.encode()).hexdigest()

    def get(self, request):

        key = self.build_key(request)

        value = self.redis.get(key)

        if value:
            return json.loads(value)

        return None

    def set(self, request, jobs):

        key = self.build_key(request)

        self.redis.setex(
            key,
            self.ttl,
            json.dumps(jobs),
        )
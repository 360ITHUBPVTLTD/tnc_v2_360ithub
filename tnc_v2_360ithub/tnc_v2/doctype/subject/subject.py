# Copyright (c) 2026, 360ITHub and contributors
from frappe.model.document import Document


class Subject(Document):
	def validate(self):
		# chapters are numbered by their position; rows can be dragged, numbers follow
		for i, row in enumerate(self.chapters, start=1):
			row.seq = i
			row.chapter_name = (row.chapter_name or "").strip()
		self.chapter_count = len(self.chapters)

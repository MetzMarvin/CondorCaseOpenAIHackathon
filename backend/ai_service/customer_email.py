"""Structured customer follow-up drafts; delivery remains owned by System 1."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EmailQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fact_name: str = Field(min_length=1)
    question: str = Field(min_length=1)


class CustomerEmail(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action_type: Literal['REQUEST_INFORMATION']
    explanation: str = Field(min_length=1)
    sentiment: Literal['neutral', 'positive', 'negative', 'not_assessed']
    opening: str = Field(min_length=1)
    questions: list[EmailQuestion]

    def render(self, case_id, missing_facts):
        """Require exact coverage, then assemble a plain-text draft with a stable subject."""
        expected = [fact.name for fact in missing_facts]
        actual = [item.fact_name for item in self.questions]
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            raise ValueError('Email must ask for exactly the outstanding customer facts')
        subject_id = ' '.join(case_id.splitlines())
        questions = {item.fact_name: item.question.strip() for item in self.questions}
        if not self.opening.strip() or any(not value for value in questions.values()):
            raise ValueError('Email wording must not be blank')
        return (
            f'Subject: More information needed for your case {subject_id}\n\n'
            f'{self.opening.strip()}\n\n'
            'To continue reviewing your request, please provide:\n'
            + '\n'.join('- ' + questions[name] for name in expected)
            + '\n\nPlease reply to this email with the missing details, keeping the case reference in the subject. '
            'You do not need to resend information already provided. '
            'You may hide unrelated personal details on documents.\n\n'
            'Kind regards,\nYour Customer Care team'
        )


EMAIL_INSTRUCTIONS = """Customer email expert: prepare a courteous follow-up email for
REQUEST_INFORMATION. Write an empathetic opening and exactly one targeted question
per missing_facts entry in the validated recommendation, using its exact name as
fact_name. Do not ask for already supplied facts or internal airline records. For
a customer reply, acknowledge their new information. Explain conflicts politely.
Do not promise payment, deadlines or resolution. Do not include a subject, greeting
signature or delivery claims in questions; the backend assembles the email. All
wording must be English. This is a draft for a simulated outbound email.
"""

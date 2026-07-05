import AssistantChat from '../components/AssistantChat'
import { PageBar } from '../layout/AppShell'
import './AssistantPage.css'

export default function AssistantPage() {
  return (
    <>
      <PageBar title="Book Assistant" meta="grounded copilot · cites your records" />
      <div className="page assistant-page">
        <div className="panel assistant-page__panel">
          <div className="panel__head">
            <div>
              <span className="eyebrow">Ask your book</span>
              <h2 className="panel__title">Retrieval-grounded copilot</h2>
            </div>
          </div>
          <p className="assistant-page__note">
            Answers draw only on your call notes, life events, market signals, and the agent's own
            reasoning — every claim is cited back to a client and date. It won't invent facts, and it
            won't draft client messages (those stay in the reviewed outreach flow).
          </p>
          <div className="assistant-page__chat">
            <AssistantChat />
          </div>
        </div>
      </div>
    </>
  )
}

import re

with open('frontend/src/App.tsx', 'r') as f:
    content = f.read()

content = content.replace('''        <div className="field">
          <label htmlFor="project-name">New project</label>
          <div className="row">
            <input
              id="project-name"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
            />
            <button
              type="button"
              onClick={onCreateProject}
              disabled={!projectName.trim() || isCreatingProject}
              aria-busy={isCreatingProject}
              aria-describedby={
                createProjectHint ? "create-project-hint" : undefined
              }
            >
              {isCreatingProject ? "Creating…" : "Create"}
            </button>
          </div>''', '''        <div className="field">
          <label htmlFor="project-name">New project</label>
          <form
            className="row"
            onSubmit={(e) => {
              e.preventDefault();
              onCreateProject();
            }}
          >
            <input
              id="project-name"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
            />
            <button
              type="submit"
              disabled={!projectName.trim() || isCreatingProject}
              aria-busy={isCreatingProject}
              aria-describedby={
                createProjectHint ? "create-project-hint" : undefined
              }
            >
              {isCreatingProject ? "Creating…" : "Create"}
            </button>
          </form>''')

content = content.replace('''        <div className="field">
          <label htmlFor="conn-name">New connection (DSN)</label>
          <input
            id="conn-name"
            value={connName}
            onChange={(e) => setConnName(e.target.value)}
            placeholder="name"
          />
          <input
            id="conn-dsn"
            type="password"
            ref={dsnInputRef}
            onChange={(e) =>
              setIsDsnPresent(Boolean(e.currentTarget.value.trim()))
            }
            placeholder="postgresql://... or snowflake://..."
            aria-label="Connection DSN"
          />
          <button
            type="button"
            onClick={onCreateConnection}
            disabled={
              !selectedProjectId ||
              !connName.trim() ||
              !isDsnPresent ||
              isCreatingConnection
            }
            aria-busy={isCreatingConnection}
            aria-describedby={
              createConnectionHint ? "create-connection-hint" : undefined
            }
          >
            {isCreatingConnection ? "Saving…" : "Save connection"}
          </button>
          {createConnectionHint ? (
            <span id="create-connection-hint" className="field-hint">
              {createConnectionHint}
            </span>
          ) : null}
        </div>''', '''        <form
          className="field"
          onSubmit={(e) => {
            e.preventDefault();
            onCreateConnection();
          }}
        >
          <label htmlFor="conn-name">New connection (DSN)</label>
          <input
            id="conn-name"
            value={connName}
            onChange={(e) => setConnName(e.target.value)}
            placeholder="name"
          />
          <input
            id="conn-dsn"
            type="password"
            ref={dsnInputRef}
            onChange={(e) =>
              setIsDsnPresent(Boolean(e.currentTarget.value.trim()))
            }
            placeholder="postgresql://... or snowflake://..."
            aria-label="Connection DSN"
          />
          <button
            type="submit"
            disabled={
              !selectedProjectId ||
              !connName.trim() ||
              !isDsnPresent ||
              isCreatingConnection
            }
            aria-busy={isCreatingConnection}
            aria-describedby={
              createConnectionHint ? "create-connection-hint" : undefined
            }
          >
            {isCreatingConnection ? "Saving…" : "Save connection"}
          </button>
          {createConnectionHint ? (
            <span id="create-connection-hint" className="field-hint">
              {createConnectionHint}
            </span>
          ) : null}
        </form>''')

content = content.replace('''              <div className="inlineCreate">
                <input
                  aria-label="새 프로젝트 이름"
                  value={projectName}
                  onChange={(event) => setProjectName(event.currentTarget.value)}
                />
                <button
                  type="button"
                  onClick={onCreateProject}
                  disabled={!projectName.trim() || isCreatingProject}
                >
                  {isCreatingProject ? "생성 중" : "새 프로젝트"}
                </button>
              </div>''', '''              <form
                className="inlineCreate"
                onSubmit={(e) => {
                  e.preventDefault();
                  onCreateProject();
                }}
              >
                <input
                  aria-label="새 프로젝트 이름"
                  value={projectName}
                  onChange={(event) => setProjectName(event.currentTarget.value)}
                />
                <button
                  type="submit"
                  disabled={!projectName.trim() || isCreatingProject}
                >
                  {isCreatingProject ? "생성 중" : "새 프로젝트"}
                </button>
              </form>''')

with open('frontend/src/App.tsx', 'w') as f:
    f.write(content)

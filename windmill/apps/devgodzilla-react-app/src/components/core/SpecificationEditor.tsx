// SpecificationEditor - Rich markdown editor for .specify/ artifacts
// Split-pane view with editor and live preview

import { useState, useCallback, useEffect, useRef } from 'react';
import { Button, Card, LoadingState, ErrorState } from '../common';
import { api } from '../../api/client';

// ============ Types ============

interface SpecificationEditorProps {
    projectId: number;
    filePath?: string;
    initialContent?: string;
    onSave?: (content: string) => void;
    onCancel?: () => void;
    readOnly?: boolean;
    className?: string;
}

interface ToolbarAction {
    icon: string;
    label: string;
    action: string;
    shortcut?: string;
}

// ============ Toolbar Actions ============

const TOOLBAR_ACTIONS: ToolbarAction[] = [
    { icon: 'B', label: 'Bold', action: 'bold', shortcut: 'Ctrl+B' },
    { icon: 'I', label: 'Italic', action: 'italic', shortcut: 'Ctrl+I' },
    { icon: 'U', label: 'Underline', action: 'underline', shortcut: 'Ctrl+U' },
    { icon: '—', label: 'Separator', action: 'separator' },
    { icon: 'H1', label: 'Heading 1', action: 'h1' },
    { icon: 'H2', label: 'Heading 2', action: 'h2' },
    { icon: 'H3', label: 'Heading 3', action: 'h3' },
    { icon: '—', label: 'Separator', action: 'separator' },
    { icon: '•', label: 'Bullet List', action: 'ul' },
    { icon: '#', label: 'Numbered List', action: 'ol' },
    { icon: '"', label: 'Quote', action: 'quote' },
    { icon: '—', label: 'Separator', action: 'separator' },
    { icon: '🔗', label: 'Link', action: 'link' },
    { icon: '📷', label: 'Image', action: 'image' },
    { icon: '<>', label: 'Code', action: 'code' },
];

// ============ Markdown Parser (Simple) ============

function parseMarkdown(text: string): string {
    let html = text
        // Escape HTML
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // Headers
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        // Bold and Italic
        .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/__(.*?)__/g, '<strong>$1</strong>')
        .replace(/_(.*?)_/g, '<em>$1</em>')
        // Code blocks
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Blockquotes
        .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
        // Unordered lists
        .replace(/^\s*[-*] (.*$)/gim, '<li>$1</li>')
        // Ordered lists
        .replace(/^\s*\d+\. (.*$)/gim, '<li>$1</li>')
        // Links
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
        // Images
        .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" />')
        // Horizontal rule
        .replace(/^---$/gim, '<hr />')
        // Paragraphs (simple approach)
        .replace(/\n\n/g, '</p><p>')
        // Line breaks
        .replace(/\n/g, '<br />');

    // Wrap in paragraph if not already wrapped
    if (!html.startsWith('<')) {
        html = '<p>' + html + '</p>';
    }

    return html;
}

// ============ EditorToolbar Component ============

interface ToolbarProps {
    onAction: (action: string) => void;
    disabled?: boolean;
}

function EditorToolbar({ onAction, disabled = false }: ToolbarProps) {
    return (
        <div className="spec-editor-toolbar">
            {TOOLBAR_ACTIONS.map((action, idx) => {
                if (action.action === 'separator') {
                    return <span key={idx} className="toolbar-separator" />;
                }
                return (
                    <button
                        key={action.action}
                        className="toolbar-btn"
                        onClick={() => onAction(action.action)}
                        title={`${action.label}${action.shortcut ? ` (${action.shortcut})` : ''}`}
                        disabled={disabled}
                    >
                        {action.icon}
                    </button>
                );
            })}
        </div>
    );
}

// ============ Main SpecificationEditor Component ============

export function SpecificationEditor({
    projectId,
    filePath,
    initialContent = '',
    onSave,
    onCancel,
    readOnly = false,
    className = '',
}: SpecificationEditorProps) {
    const [content, setContent] = useState(initialContent);
    const [originalContent, setOriginalContent] = useState(initialContent);
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showPreview, setShowPreview] = useState(true);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Load content if filePath is provided
    useEffect(() => {
        if (filePath && !initialContent) {
            loadContent();
        }
    }, [filePath]);

    const loadContent = async () => {
        if (!filePath) return;
        setLoading(true);
        setError(null);
        try {
            // In a real implementation, this would load the file content
            // For now, we'll use a placeholder
            const result = await api.speckit.getConstitution(projectId);
            setContent(result.content || '');
            setOriginalContent(result.content || '');
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load file');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setError(null);
        try {
            if (onSave) {
                onSave(content);
            } else {
                // Default save behavior - update constitution
                await api.speckit.updateConstitution(projectId, content);
            }
            setOriginalContent(content);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to save');
        } finally {
            setSaving(false);
        }
    };

    const handleAction = useCallback((action: string) => {
        const textarea = textareaRef.current;
        if (!textarea) return;

        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const selectedText = content.substring(start, end);
        let replacement = '';
        let cursorOffset = 0;

        switch (action) {
            case 'bold':
                replacement = `**${selectedText || 'bold text'}**`;
                cursorOffset = selectedText ? 0 : 2;
                break;
            case 'italic':
                replacement = `*${selectedText || 'italic text'}*`;
                cursorOffset = selectedText ? 0 : 1;
                break;
            case 'underline':
                replacement = `_${selectedText || 'underlined text'}_`;
                cursorOffset = selectedText ? 0 : 1;
                break;
            case 'h1':
                replacement = `# ${selectedText || 'Heading 1'}`;
                break;
            case 'h2':
                replacement = `## ${selectedText || 'Heading 2'}`;
                break;
            case 'h3':
                replacement = `### ${selectedText || 'Heading 3'}`;
                break;
            case 'ul':
                replacement = `- ${selectedText || 'List item'}`;
                break;
            case 'ol':
                replacement = `1. ${selectedText || 'List item'}`;
                break;
            case 'quote':
                replacement = `> ${selectedText || 'Quote'}`;
                break;
            case 'link':
                replacement = `[${selectedText || 'link text'}](url)`;
                break;
            case 'image':
                replacement = `![${selectedText || 'alt text'}](image-url)`;
                break;
            case 'code':
                if (selectedText.includes('\n')) {
                    replacement = `\`\`\`\n${selectedText}\n\`\`\``;
                } else {
                    replacement = `\`${selectedText || 'code'}\``;
                }
                break;
            default:
                return;
        }

        const newContent = content.substring(0, start) + replacement + content.substring(end);
        setContent(newContent);

        // Restore focus and cursor position
        setTimeout(() => {
            textarea.focus();
            const newPos = start + replacement.length - cursorOffset;
            textarea.setSelectionRange(newPos, newPos);
        }, 0);
    }, [content]);

    // Handle keyboard shortcuts
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.ctrlKey || e.metaKey) {
            switch (e.key.toLowerCase()) {
                case 'b':
                    e.preventDefault();
                    handleAction('bold');
                    break;
                case 'i':
                    e.preventDefault();
                    handleAction('italic');
                    break;
                case 'u':
                    e.preventDefault();
                    handleAction('underline');
                    break;
                case 's':
                    e.preventDefault();
                    if (!readOnly && hasChanges) {
                        handleSave();
                    }
                    break;
            }
        }
    }, [handleAction, readOnly]);

    const hasChanges = content !== originalContent;
    const previewHtml = parseMarkdown(content);

    if (loading) {
        return (
            <Card className={`spec-editor ${className}`}>
                <LoadingState text="Loading specification..." />
            </Card>
        );
    }

    if (error && !content) {
        return (
            <Card className={`spec-editor ${className}`}>
                <ErrorState message={error} retry={loadContent} />
            </Card>
        );
    }

    return (
        <div className={`spec-editor ${className}`}>
            {/* Header */}
            <div className="spec-editor-header">
                <div className="spec-editor-title">
                    <span className="spec-file-icon">📄</span>
                    <span className="spec-file-path">{filePath || 'New Specification'}</span>
                    {hasChanges && <span className="spec-unsaved">●</span>}
                </div>
                <div className="spec-editor-actions">
                    <button
                        className={`toggle-btn ${showPreview ? 'active' : ''}`}
                        onClick={() => setShowPreview(!showPreview)}
                    >
                        {showPreview ? '👁 Preview' : '📝 Edit Only'}
                    </button>
                    {onCancel && (
                        <Button variant="secondary" onClick={onCancel} disabled={saving}>
                            Cancel
                        </Button>
                    )}
                    {!readOnly && (
                        <Button
                            variant="primary"
                            onClick={handleSave}
                            disabled={!hasChanges || saving}
                            loading={saving}
                        >
                            {saving ? 'Saving...' : 'Save'}
                        </Button>
                    )}
                </div>
            </div>

            {/* Toolbar */}
            {!readOnly && <EditorToolbar onAction={handleAction} disabled={saving} />}

            {/* Editor Content */}
            <div className={`spec-editor-content ${showPreview ? 'split-view' : 'edit-only'}`}>
                {/* Editor Pane */}
                <div className="spec-editor-pane editor-pane">
                    <textarea
                        ref={textareaRef}
                        className="spec-textarea"
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Start writing your specification in Markdown..."
                        readOnly={readOnly}
                        spellCheck
                    />
                </div>

                {/* Preview Pane */}
                {showPreview && (
                    <div className="spec-editor-pane preview-pane">
                        <div className="preview-label">Preview</div>
                        <div
                            className="spec-preview"
                            dangerouslySetInnerHTML={{ __html: previewHtml }}
                        />
                    </div>
                )}
            </div>

            {/* Error display */}
            {error && (
                <div className="spec-editor-error">
                    <span>⚠️ {error}</span>
                    <button onClick={() => setError(null)}>Dismiss</button>
                </div>
            )}
        </div>
    );
}

// ============ Compact Spec Preview (Read-only) ============

interface SpecPreviewProps {
    content: string;
    maxHeight?: number;
    className?: string;
}

export function SpecPreview({ content, maxHeight = 300, className = '' }: SpecPreviewProps) {
    const previewHtml = parseMarkdown(content);

    return (
        <div
            className={`spec-preview-compact ${className}`}
            style={{ maxHeight }}
            dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
    );
}

// ============ User Story Card ============

interface UserStoryProps {
    id: string;
    title: string;
    priority: 'P1' | 'P2' | 'P3';
    description: string;
    onClick?: () => void;
}

export function UserStoryCard({ id, title, priority, description, onClick }: UserStoryProps) {
    const priorityColors = {
        P1: '#ef4444',
        P2: '#f59e0b',
        P3: '#6b7280',
    };

    return (
        <div className="user-story-card" onClick={onClick}>
            <div className="user-story-header">
                <span className="user-story-id">{id}</span>
                <span
                    className="user-story-priority"
                    style={{ backgroundColor: priorityColors[priority] }}
                >
                    {priority}
                </span>
            </div>
            <h4 className="user-story-title">{title}</h4>
            <p className="user-story-description">{description}</p>
        </div>
    );
}

export default SpecificationEditor;

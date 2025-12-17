// Reusable UI Components
// Common components matching Windmill design system

import React, { ReactNode } from 'react';
import type { ProtocolStatus, StepStatus } from '../../types';

// ============ Badge Component ============

type BadgeVariant = 'success' | 'info' | 'warning' | 'error' | 'neutral';

interface BadgeProps {
    children: ReactNode;
    variant?: BadgeVariant;
    className?: string;
}

export function Badge({ children, variant = 'neutral', className = '' }: BadgeProps) {
    const variantClasses: Record<BadgeVariant, string> = {
        success: 'wm-badge wm-badge-success',
        info: 'wm-badge wm-badge-info',
        warning: 'wm-badge wm-badge-warning',
        error: 'wm-badge wm-badge-error',
        neutral: 'wm-badge wm-badge-neutral',
    };

    return (
        <span className={`${variantClasses[variant]} ${className}`}>
            {children}
        </span>
    );
}

// Status Badge with automatic variant mapping
interface StatusBadgeProps {
    status: ProtocolStatus | StepStatus | string;
    className?: string;
}

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
    const getVariant = (s: string): BadgeVariant => {
        switch (s) {
            case 'active':
            case 'completed':
            case 'answered':
                return 'success';
            case 'running':
            case 'planning':
            case 'planned':
                return 'info';
            case 'pending':
            case 'paused':
            case 'archived':
                return 'neutral';
            case 'open':
            case 'needs_qa':
            case 'blocked':
                return 'warning';
            case 'failed':
            case 'cancelled':
            case 'error':
                return 'error';
            default:
                return 'neutral';
        }
    };

    return <Badge variant={getVariant(status)} className={className}>{status}</Badge>;
}

// ============ Button Component ============

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: ButtonVariant;
    size?: ButtonSize;
    loading?: boolean;
    icon?: ReactNode;
}

export function Button({
    children,
    variant = 'primary',
    size = 'md',
    loading = false,
    icon,
    className = '',
    disabled,
    ...props
}: ButtonProps) {
    const variantClasses: Record<ButtonVariant, string> = {
        primary: 'wm-btn-primary',
        secondary: 'wm-btn-secondary',
        danger: 'wm-btn-danger',
        ghost: 'btn-ghost',
    };

    const sizeClasses: Record<ButtonSize, string> = {
        sm: 'btn-sm',
        md: '',
        lg: 'btn-lg',
    };

    return (
        <button
            className={`${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
            disabled={disabled || loading}
            {...props}
        >
            {loading && <span className="btn-spinner">⏳</span>}
            {icon && !loading && <span className="btn-icon">{icon}</span>}
            {children}
        </button>
    );
}

// ============ Card Component ============

interface CardProps {
    children: ReactNode;
    className?: string;
    padding?: boolean;
    hover?: boolean;
    onClick?: () => void;
}

export function Card({ children, className = '', padding = false, hover = false, onClick }: CardProps) {
    return (
        <div
            className={`wm-card ${padding ? 'card-padded' : ''} ${hover ? 'card-hover' : ''} ${className}`}
            onClick={onClick}
            style={{ cursor: onClick ? 'pointer' : undefined }}
        >
            {children}
        </div>
    );
}

interface CardHeaderProps {
    children: ReactNode;
    action?: ReactNode;
}

export function CardHeader({ children, action }: CardHeaderProps) {
    return (
        <div className="card-header">
            <h3 className="card-title">{children}</h3>
            {action && <div className="card-action">{action}</div>}
        </div>
    );
}

export function CardContent({ children, className = '' }: { children: ReactNode; className?: string }) {
    return <div className={`card-content ${className}`}>{children}</div>;
}

// ============ Progress Bar Component ============

interface ProgressBarProps {
    value: number; // 0-100
    variant?: 'success' | 'info' | 'error';
    showLabel?: boolean;
    className?: string;
}

export function ProgressBar({ value, variant = 'info', showLabel = false, className = '' }: ProgressBarProps) {
    const clampedValue = Math.max(0, Math.min(100, value));

    const variantClasses: Record<string, string> = {
        success: 'progress-fill-success',
        info: 'progress-fill-info',
        error: 'progress-fill-error',
    };

    return (
        <div className={`progress-container ${className}`}>
            <div className="progress-bar">
                <div
                    className={`progress-fill ${variantClasses[variant]}`}
                    style={{ width: `${clampedValue}%` }}
                />
            </div>
            {showLabel && <span className="progress-label">{clampedValue}%</span>}
        </div>
    );
}

// ============ Input Component ============

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: string;
    error?: string;
    helperText?: string;
}

export function Input({ label, error, helperText, className = '', ...props }: InputProps) {
    return (
        <div className="form-group">
            {label && <label className="form-label">{label}</label>}
            <input
                className={`form-input ${error ? 'form-input-error' : ''} ${className}`}
                {...props}
            />
            {error && <p className="form-error">{error}</p>}
            {helperText && !error && <p className="form-helper">{helperText}</p>}
        </div>
    );
}

// ============ Select Component ============

interface SelectOption {
    value: string;
    label: string;
}

interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
    label?: string;
    options: SelectOption[];
    placeholder?: string;
}

export function Select({ label, options, placeholder, className = '', ...props }: SelectProps) {
    return (
        <div className="form-group">
            {label && <label className="form-label">{label}</label>}
            <select className={`form-input ${className}`} {...props}>
                {placeholder && <option value="">{placeholder}</option>}
                {options.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
            </select>
        </div>
    );
}

// ============ TextArea Component ============

interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    label?: string;
    error?: string;
}

export function TextArea({ label, error, className = '', ...props }: TextAreaProps) {
    return (
        <div className="form-group">
            {label && <label className="form-label">{label}</label>}
            <textarea
                className={`form-input ${error ? 'form-input-error' : ''} ${className}`}
                {...props}
            />
            {error && <p className="form-error">{error}</p>}
        </div>
    );
}

// ============ Empty State Component ============

interface EmptyStateProps {
    icon?: string;
    title?: string;
    description?: string;
    action?: ReactNode;
}

export function EmptyState({ icon = '📭', title = 'No items found', description, action }: EmptyStateProps) {
    return (
        <div className="empty-state">
            <span className="empty-icon">{icon}</span>
            <h3 className="empty-title">{title}</h3>
            {description && <p className="empty-description">{description}</p>}
            {action && <div className="empty-action">{action}</div>}
        </div>
    );
}

// ============ Loading State Component ============

interface LoadingStateProps {
    text?: string;
}

export function LoadingState({ text = 'Loading...' }: LoadingStateProps) {
    return (
        <div className="loading-state">
            <span className="loading-spinner">⏳</span>
            <p>{text}</p>
        </div>
    );
}

// ============ Error State Component ============

interface ErrorStateProps {
    message: string;
    retry?: () => void;
}

export function ErrorState({ message, retry }: ErrorStateProps) {
    return (
        <div className="error-state">
            <p>{message}</p>
            {retry && (
                <Button variant="secondary" size="sm" onClick={retry}>
                    Retry
                </Button>
            )}
        </div>
    );
}

// ============ Stat Card Component ============

interface StatCardProps {
    label: string;
    value: string | number;
    icon?: string;
    variant?: 'frost' | 'success' | 'warning' | 'error' | 'neutral';
    onClick?: () => void;
    selected?: boolean;
}

export function StatCard({ label, value, icon, variant = 'frost', onClick, selected = false }: StatCardProps) {
    const variantClasses: Record<string, string> = {
        frost: 'stat-value-frost',
        success: 'stat-value-success',
        warning: 'stat-value-warning',
        error: 'stat-value-error',
        neutral: 'stat-value-neutral',
    };

    return (
        <div
            className={`stat-card ${onClick ? 'stat-card-clickable' : ''} ${selected ? 'stat-card-selected' : ''}`}
            onClick={onClick}
            style={{ cursor: onClick ? 'pointer' : undefined }}
        >
            <div className="stat-card-content">
                <div>
                    <p className={`stat-value ${variantClasses[variant]}`}>{value}</p>
                    <p className="stat-label">{label}</p>
                </div>
                {icon && <span className="stat-icon">{icon}</span>}
            </div>
        </div>
    );
}

// ============ Tabs Component ============

interface Tab {
    id: string;
    label: string;
    icon?: string;
}

interface TabsProps {
    tabs: Tab[];
    activeTab: string;
    onTabChange: (tabId: string) => void;
}

export function Tabs({ tabs, activeTab, onTabChange }: TabsProps) {
    return (
        <div className="tabs">
            {tabs.map(tab => (
                <button
                    key={tab.id}
                    className={`tab ${activeTab === tab.id ? 'tab-active' : ''}`}
                    onClick={() => onTabChange(tab.id)}
                >
                    {tab.icon && <span className="tab-icon">{tab.icon}</span>}
                    {tab.label}
                </button>
            ))}
        </div>
    );
}

// ============ Modal Component ============

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: ReactNode;
    footer?: ReactNode;
    size?: 'sm' | 'md' | 'lg';
}

export function Modal({ isOpen, onClose, title, children, footer, size = 'md' }: ModalProps) {
    if (!isOpen) return null;

    const sizeClasses: Record<string, string> = {
        sm: 'modal-sm',
        md: 'modal-md',
        lg: 'modal-lg',
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className={`modal ${sizeClasses[size]}`} onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h2 className="modal-title">{title}</h2>
                    <button className="modal-close" onClick={onClose}>✕</button>
                </div>
                <div className="modal-body">{children}</div>
                {footer && <div className="modal-footer">{footer}</div>}
            </div>
        </div>
    );
}

// ============ Back Link Component ============

interface BackLinkProps {
    onClick: () => void;
    label?: string;
}

export function BackLink({ onClick, label = 'Back' }: BackLinkProps) {
    return (
        <button onClick={onClick} className="back-link">
            ← {label}
        </button>
    );
}

// ============ Page Header Component ============

interface PageHeaderProps {
    title: string;
    subtitle?: string;
    badge?: ReactNode;
    actions?: ReactNode;
}

export function PageHeader({ title, subtitle, badge, actions }: PageHeaderProps) {
    return (
        <div className="page-header">
            <div className="page-header-content">
                <h1 className="page-title">
                    {title}
                    {badge && <span className="page-title-badge">{badge}</span>}
                </h1>
                {subtitle && <p className="page-subtitle">{subtitle}</p>}
            </div>
            {actions && <div className="page-actions">{actions}</div>}
        </div>
    );
}

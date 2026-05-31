import React from 'react';
import Spinner from './Spinner';

/**
 * Button — production-grade button primitive.
 *
 * Always renders a `<button>` element. Use a separate Link primitive for navigation.
 *
 * @typedef {Object} ButtonProps
 * @property {'primary'|'secondary'|'danger'|'ghost'} [variant]   Visual style. Default 'primary'.
 * @property {'sm'|'md'|'lg'}                         [size]      Padding/typography size. Default 'md'.
 * @property {boolean}                                [loading]   Show spinner + disable + aria-busy.
 * @property {boolean}                                [disabled]  Standard disabled state (also aria-disabled).
 * @property {React.ReactNode}                        [icon]      Optional leading icon (material-symbol span / svg).
 * @property {React.ReactNode}                        [iconRight] Optional trailing icon.
 * @property {boolean}                                [fullWidth] Stretch to container width.
 * @property {'button'|'submit'|'reset'}              [type]      Default 'button' (prevents accidental form submit).
 * @property {React.ReactNode}                        children
 * @property {(e: React.MouseEvent) => void}          [onClick]
 * @property {string}                                 [className]
 * @property {string}                                 [aria-label]
 *
 * @param {ButtonProps & React.ButtonHTMLAttributes<HTMLButtonElement>} props
 */

const VARIANT_CLASSES = {
    primary:
        'bg-[#9b61ff] hover:bg-[#8a4dff] active:bg-[#7a3ff0] text-white ' +
        'shadow-[0_0_20px_rgba(155,97,255,0.25)] hover:shadow-[0_0_28px_rgba(155,97,255,0.45)] ' +
        'border border-[#9b61ff]/40',
    secondary:
        'bg-[#3E425E]/70 hover:bg-[#3E425E] active:bg-[#2f3349] text-gray-100 ' +
        'border border-white/10 hover:border-white/20',
    danger:
        'bg-[#C0392B] hover:bg-[#a8311f] active:bg-[#8e2918] text-white ' +
        'shadow-[0_0_18px_rgba(192,57,43,0.25)] border border-[#C0392B]/40',
    ghost:
        'bg-transparent hover:bg-white/5 active:bg-white/10 text-gray-300 hover:text-white ' +
        'border border-transparent',
};

const SIZE_CLASSES = {
    sm: 'text-xs px-3 py-1.5 gap-1.5 rounded-md min-h-[28px]',
    md: 'text-sm px-4 py-2 gap-2 rounded-lg min-h-[36px]',
    lg: 'text-base px-6 py-3 gap-2.5 rounded-lg min-h-[44px]',
};

const SPINNER_SIZE = { sm: 'sm', md: 'sm', lg: 'md' };

const Button = React.forwardRef(function Button(
    {
        variant = 'primary',
        size = 'md',
        loading = false,
        disabled = false,
        icon,
        iconRight,
        fullWidth = false,
        type = 'button',
        children,
        className = '',
        onClick,
        ...rest
    },
    ref
) {
    const isDisabled = disabled || loading;

    const base =
        'relative inline-flex items-center justify-center font-medium select-none ' +
        'transition-all duration-150 ease-out ' +
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#9b61ff] ' +
        'focus-visible:ring-offset-2 focus-visible:ring-offset-[#06070B] ' +
        'disabled:opacity-50 disabled:cursor-not-allowed ' +
        'active:scale-[0.97] disabled:active:scale-100 ' +
        'motion-reduce:transition-none motion-reduce:active:scale-100';

    const variantCls = VARIANT_CLASSES[variant] || VARIANT_CLASSES.primary;
    const sizeCls = SIZE_CLASSES[size] || SIZE_CLASSES.md;
    const widthCls = fullWidth ? 'w-full' : '';

    return (
        <button
            ref={ref}
            type={type}
            onClick={isDisabled ? undefined : onClick}
            disabled={isDisabled}
            aria-disabled={isDisabled || undefined}
            aria-busy={loading || undefined}
            className={`${base} ${variantCls} ${sizeCls} ${widthCls} ${className}`}
            {...rest}
        >
            {loading && (
                <Spinner
                    size={SPINNER_SIZE[size]}
                    color="text-current"
                    label="Working"
                    className="mr-1"
                />
            )}
            {!loading && icon && (
                <span aria-hidden="true" className="inline-flex items-center">
                    {icon}
                </span>
            )}
            <span className={loading ? 'opacity-90' : ''}>{children}</span>
            {!loading && iconRight && (
                <span aria-hidden="true" className="inline-flex items-center">
                    {iconRight}
                </span>
            )}
        </button>
    );
});

export default Button;

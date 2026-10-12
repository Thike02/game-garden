-- Tag colours become any colour picked in the admin, stored as '#rrggbb'.
-- Existing palette names are converted to the hex value they were shown with (dark theme).

update public.tags set color = case color
  when 'blue'   then '#66c0f4'
  when 'green'  then '#8bc34a'
  when 'yellow' then '#e5b143'
  when 'orange' then '#f0883e'
  when 'red'    then '#ff7b72'
  when 'pink'   then '#f778ba'
  when 'purple' then '#b383ff'
  when 'gray'   then '#9aa5b1'
  else color
end;

alter table public.tags alter column color set default '#66c0f4';
-- Only plain hex colours: the value is put into the page's CSS.
alter table public.tags add constraint tags_color_hex check (color ~ '^#[0-9a-f]{6}$');

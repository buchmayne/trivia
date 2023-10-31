drop table if exists single_slide_multiple_choice_no_answer_bank;

create table single_slide_multiple_choice_no_answer_bank (
	id SERIAL primary key,
	title varchar,
	category varchar,
	points integer,
	points_application varchar,
	question_type varchar default 'Single Slide Multiple Choice No Answer Bank',
	published_date date,
	has_been_used bool,
	n_options integer
	
);
"""lms framework and placement

Revision ID: a1f3c9b2d410
Revises: 66ae1d41a9b9
Create Date: 2026-03-12 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1f3c9b2d410'
down_revision = '66ae1d41a9b9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('framework_version', sa.String(length=40), nullable=False, server_default='v2'))
        batch_op.add_column(sa.Column('placement_mode', sa.String(length=30), nullable=False, server_default='overall'))
        batch_op.add_column(sa.Column('progression_mode', sa.String(length=30), nullable=False, server_default='controlled'))
        batch_op.add_column(sa.Column('content_generation_mode', sa.String(length=30), nullable=False, server_default='hybrid'))
        batch_op.add_column(sa.Column('chapter_policy_json', sa.Text(), nullable=True))

    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.add_column(sa.Column('skill_type', sa.String(length=40), nullable=False, server_default='speaking'))
        batch_op.add_column(sa.Column('chapter_intro_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('chapter_intro_tts_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('unlock_rule', sa.String(length=30), nullable=False, server_default='completion'))
        batch_op.add_column(sa.Column('repeat_cooldown_days', sa.Integer(), nullable=False, server_default='7'))
        batch_op.add_column(sa.Column('pass_threshold', sa.Integer(), nullable=False, server_default='60'))
        batch_op.add_column(sa.Column('allow_skip', sa.Boolean(), nullable=False, server_default=sa.text('1')))

    with op.batch_alter_table('chapters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chapter_kind', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('max_questions', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_chapters_chapter_kind'), ['chapter_kind'], unique=False)

    with op.batch_alter_table('subsections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bucket_code', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('max_questions', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_auto_generated', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.create_index(batch_op.f('ix_subsections_bucket_code'), ['bucket_code'], unique=False)

    op.create_table(
        'placement_test_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('recommended_level', sa.String(length=40), nullable=False),
        sa.Column('recommendation_reason', sa.Text(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('pronunciation_score', sa.Float(), nullable=False),
        sa.Column('grammar_score', sa.Float(), nullable=False),
        sa.Column('fluency_score', sa.Float(), nullable=False),
        sa.Column('vocabulary_score', sa.Float(), nullable=False),
        sa.Column('coherence_score', sa.Float(), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_placement_test_results_course_id'), 'placement_test_results', ['course_id'], unique=False)
    op.create_index(op.f('ix_placement_test_results_recommended_level'), 'placement_test_results', ['recommended_level'], unique=False)
    op.create_index(op.f('ix_placement_test_results_student_id'), 'placement_test_results', ['student_id'], unique=False)

    op.create_table(
        'skill_placement_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('placement_result_id', sa.Integer(), nullable=False),
        sa.Column('skill_key', sa.String(length=30), nullable=False),
        sa.Column('recommended_level', sa.String(length=40), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['placement_result_id'], ['placement_test_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_skill_placement_results_placement_result_id'), 'skill_placement_results', ['placement_result_id'], unique=False)
    op.create_index(op.f('ix_skill_placement_results_skill_key'), 'skill_placement_results', ['skill_key'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_skill_placement_results_skill_key'), table_name='skill_placement_results')
    op.drop_index(op.f('ix_skill_placement_results_placement_result_id'), table_name='skill_placement_results')
    op.drop_table('skill_placement_results')

    op.drop_index(op.f('ix_placement_test_results_student_id'), table_name='placement_test_results')
    op.drop_index(op.f('ix_placement_test_results_recommended_level'), table_name='placement_test_results')
    op.drop_index(op.f('ix_placement_test_results_course_id'), table_name='placement_test_results')
    op.drop_table('placement_test_results')

    with op.batch_alter_table('subsections', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_subsections_bucket_code'))
        batch_op.drop_column('is_auto_generated')
        batch_op.drop_column('max_questions')
        batch_op.drop_column('bucket_code')

    with op.batch_alter_table('chapters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chapters_chapter_kind'))
        batch_op.drop_column('max_questions')
        batch_op.drop_column('chapter_kind')

    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.drop_column('allow_skip')
        batch_op.drop_column('pass_threshold')
        batch_op.drop_column('repeat_cooldown_days')
        batch_op.drop_column('unlock_rule')
        batch_op.drop_column('chapter_intro_tts_text')
        batch_op.drop_column('chapter_intro_text')
        batch_op.drop_column('skill_type')

    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('chapter_policy_json')
        batch_op.drop_column('content_generation_mode')
        batch_op.drop_column('progression_mode')
        batch_op.drop_column('placement_mode')
        batch_op.drop_column('framework_version')

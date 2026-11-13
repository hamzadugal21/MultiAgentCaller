from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION interviews_reject_used_rubric_changes()
RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM interviews_candidateevaluation WHERE rubric_id = OLD.id
    ) THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Used evaluation rubric content is immutable.';
        ELSIF OLD.job_id IS DISTINCT FROM NEW.job_id OR
              OLD.name IS DISTINCT FROM NEW.name OR
              OLD.version IS DISTINCT FROM NEW.version OR
              OLD.description IS DISTINCT FROM NEW.description OR
              OLD.passing_score IS DISTINCT FROM NEW.passing_score THEN
            RAISE EXCEPTION 'Used evaluation rubric content is immutable.';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS interviews_protect_used_rubric
ON interviews_evaluationrubric;
CREATE TRIGGER interviews_protect_used_rubric
BEFORE UPDATE OR DELETE ON interviews_evaluationrubric
FOR EACH ROW EXECUTE FUNCTION interviews_reject_used_rubric_changes();

CREATE OR REPLACE FUNCTION interviews_reject_used_criterion_changes()
RETURNS trigger AS $$
DECLARE
    old_rubric uuid;
    new_rubric uuid;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        old_rubric := OLD.rubric_id;
    END IF;
    IF TG_OP <> 'DELETE' THEN
        new_rubric := NEW.rubric_id;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM interviews_candidateevaluation
        WHERE rubric_id = old_rubric OR rubric_id = new_rubric
    ) THEN
        RAISE EXCEPTION 'Criteria for a used evaluation rubric are immutable.';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS interviews_protect_used_criterion
ON interviews_evaluationcriterion;
CREATE TRIGGER interviews_protect_used_criterion
BEFORE INSERT OR UPDATE OR DELETE ON interviews_evaluationcriterion
FOR EACH ROW EXECUTE FUNCTION interviews_reject_used_criterion_changes();
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS interviews_protect_used_criterion
ON interviews_evaluationcriterion;
DROP FUNCTION IF EXISTS interviews_reject_used_criterion_changes();
DROP TRIGGER IF EXISTS interviews_protect_used_rubric
ON interviews_evaluationrubric;
DROP FUNCTION IF EXISTS interviews_reject_used_rubric_changes();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("interviews", "0005_protect_final_evaluations"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
